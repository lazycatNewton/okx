"""M25 统计与历史采集单元测试（编译级 + fake fetch，不依赖真实网络/数据库）。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from okx_backend.db.models import M25Metric
from okx_backend.okx_client.rest import OkxRestError
from okx_backend.services.m25_stats import (
    _poll_limit,
    _s01_row_to_payload,
    _s04_row_to_payload,
    _s05_row_to_payload,
    _throttle,
    backfill_array_metric,
    backfill_ny_day_metric,
    ny_day_open,
    period_seconds,
    poll_interval_seconds,
)
from okx_backend.services.ny_day import ny_day_start_ms


def test_period_seconds_covers_all_confirmed_periods() -> None:
    assert period_seconds("5m") == 300.0
    assert period_seconds("15m") == 900.0
    assert period_seconds("1H") == 3600.0
    assert period_seconds("1D") == 86400.0


def test_s01_row_to_payload_parses_ts_and_ratio() -> None:
    ts_ms, payload = _s01_row_to_payload(["1701417600000", "1.1739"])
    assert ts_ms == 1701417600000
    assert payload == {"ts": "1701417600000", "longShortAcctRatio": "1.1739"}


def test_s04_row_to_payload_parses_sell_then_buy_order() -> None:
    """官方数组顺序是 [ts, sellVol, buyVol]，不能颠倒。"""

    ts_ms, payload = _s04_row_to_payload(["1701417600000", "200", "380"])
    assert ts_ms == 1701417600000
    assert payload == {"ts": "1701417600000", "sellVol": "200", "buyVol": "380"}


def test_s05_row_to_payload_parses_oi_triplet() -> None:
    ts_ms, payload = _s05_row_to_payload(["1701417600000", "731377.5", "111", "8888888"])
    assert ts_ms == 1701417600000
    assert payload == {
        "ts": "1701417600000", "oi": "731377.5", "oiCcy": "111", "oiUsd": "8888888",
    }


@pytest.mark.asyncio
async def test_backfill_array_metric_stops_at_cutoff(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: list[tuple] = []

    async def fake_store(metric, query_key, period, unit, ts_ms, raw_payload):  # noqa: ANN001
        stored.append((metric, query_key, period, unit, ts_ms))

    monkeypatch.setattr("okx_backend.services.m25_stats._store_stat", fake_store)

    now = datetime(2026, 9, 13, tzinfo=UTC)
    cutoff_ms = int(now.timestamp() * 1000) - 7 * 86400 * 1000
    # 第一页返回满 100 条（均晚于 cutoff），表示官方仍有更旧数据可翻页；
    # 第二页只有 1 条且早于 cutoff，触发停止。真实 API 语义：返回条数小于上限
    # 才代表数据已耗尽，所以第一页必须填满，否则测试会与 backfill_array_metric
    # 的“返回行数<100 视为耗尽”提前退出逻辑产生假阳性。
    page_one = [[str(cutoff_ms + 100_000 - i), "1.1"] for i in range(100)]
    pages = [page_one, [[str(cutoff_ms - 10_000), "1.3"]]]

    async def fake_fetch(end: str | None) -> list[list[str]]:
        return pages.pop(0) if pages else []

    saved = await backfill_array_metric(
        fetch=fake_fetch,
        metric=M25Metric.S01,
        query_key="BTC-USDT-SWAP",
        period="5m",
        unit=None,
        row_to_payload=_s01_row_to_payload,
        cutoff_days=7,
        now=now,
    )
    assert saved == 101
    assert len(stored) == 101


@pytest.mark.asyncio
async def test_backfill_array_metric_stops_when_page_short(monkeypatch: pytest.MonkeyPatch) -> None:
    """未触及 cutoff 但返回行数小于 100（页大小上限）时也应停止，避免死循环请求空页。"""

    async def fake_store(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return None

    monkeypatch.setattr("okx_backend.services.m25_stats._store_stat", fake_store)

    now = datetime(2026, 9, 13, tzinfo=UTC)
    call_count = 0

    async def fake_fetch(end: str | None) -> list[list[str]]:
        nonlocal call_count
        call_count += 1
        # 返回未过期但数量 < 100 的一页，代表官方数据已耗尽。
        return [[str(int(now.timestamp() * 1000)), "1", "2", "3"]]

    saved = await backfill_array_metric(
        fetch=fake_fetch,
        metric=M25Metric.S05,
        query_key="BTC-USDT-SWAP",
        period="5m",
        unit=None,
        row_to_payload=_s05_row_to_payload,
        cutoff_days=7,
        now=now,
    )
    assert saved == 1
    assert call_count == 1


@pytest.mark.asyncio
async def test_throttle_serializes_concurrent_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """回归测试：修复真实 429 事故——多个并发回填任务必须被全局节流串行化，
    不能在同一时刻对同一端点发出一批并发首请求（此前 S04 单产品 3 周期x3 单位=9 个
    并发请求瞬间超过 OKX 5 次/2s 限速，实测触发 429 Too Many Requests）。"""

    import okx_backend.services.m25_stats as m25_stats

    monkeypatch.setattr(m25_stats, "_global_last_request_at", 0.0)
    monkeypatch.setattr(m25_stats, "_GLOBAL_MIN_INTERVAL_SECONDS", 0.05)

    call_times: list[float] = []

    async def fake_call() -> None:
        await _throttle()
        call_times.append(asyncio.get_event_loop().time())

    await asyncio.gather(*(fake_call() for _ in range(5)))

    call_times.sort()
    gaps = [b - a for a, b in zip(call_times, call_times[1:], strict=False)]
    assert all(gap >= 0.04 for gap in gaps), f"节流未生效，间隔过短: {gaps}"


@pytest.mark.asyncio
async def test_backfill_m25_isolates_one_failing_product_from_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归测试：修复真实事故——`backfill_m25` 此前用不带 `return_exceptions=True`
    的 `asyncio.gather`，任何一个 (指标, 产品, 周期) 组合的 OKX 报错都会让全部已选
    产品/指标的回填一并抛异常、颗粒无收。这里让 SPCX 的 S05 失败，断言 BTC 的其余
    指标仍然完整落库。"""

    import okx_backend.services.m25_stats as m25_stats

    stored: list[tuple] = []

    async def fake_store(metric, query_key, period, unit, ts_ms, raw_payload):  # noqa: ANN001
        stored.append((metric, query_key))

    monkeypatch.setattr(m25_stats, "_store_stat", fake_store)
    monkeypatch.setattr(m25_stats, "_throttle", AsyncMock())

    class _FakeClient:
        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get_long_short_account_ratio_contract(self, inst_id, **kwargs):  # noqa: ANN001
            return [[str(int(datetime.now(UTC).timestamp() * 1000)), "1.1"]]

        async def get_open_interest_history(self, inst_id, **kwargs):  # noqa: ANN001
            if inst_id.startswith("SPCX"):
                raise OkxRestError("51001", "Instrument ID does not exist")
            return [[str(int(datetime.now(UTC).timestamp() * 1000)), "1", "2", "3"]]

        async def get_taker_volume_contract(self, inst_id, **kwargs):  # noqa: ANN001
            return [[str(int(datetime.now(UTC).timestamp() * 1000)), "1", "2"]]

    monkeypatch.setattr(m25_stats, "OkxRestClient", _FakeClient)

    await m25_stats.backfill_m25([("BTC-USDT-SWAP", "SWAP"), ("SPCX-USDT-SWAP", "SWAP")])

    btc_metrics = {metric for metric, key in stored if key == "BTC-USDT-SWAP"}
    spcx_metrics = {metric for metric, key in stored if key == "SPCX-USDT-SWAP"}
    assert m25_stats.M25Metric.S05 in btc_metrics, "SPCX 的 S05 失败不应连累 BTC 的 S05"
    assert {m25_stats.M25Metric.S01, m25_stats.M25Metric.S04} <= btc_metrics
    # 失败的产品只丢掉失败的那个指标，它自己的其余指标照常落库。
    assert m25_stats.M25Metric.S05 not in spcx_metrics
    assert {m25_stats.M25Metric.S01, m25_stats.M25Metric.S04} <= spcx_metrics


# -- 纽约自然日日线（1D 改由官方 1H 派生）-----------------------------------
def test_daily_polling_uses_the_hourly_source_cadence_and_lookback() -> None:
    """`1D` 不能每 24 小时才拉一次：它请求的是 1H，必须每小时修正当天的日线。"""

    assert poll_interval_seconds("1D") == 3600.0
    assert poll_interval_seconds("5m") == 300.0
    # 48 根 1H 才能完整覆盖当前纽约自然日与前一个自然日（含 25 小时的冬令时回拨日）。
    assert _poll_limit("1D") == 48
    assert _poll_limit("5m") == 5


@pytest.mark.asyncio
async def test_ny_day_backfill_requests_hourly_and_stores_one_row_per_new_york_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 9, 21, 18, tzinfo=UTC)
    day_now = ny_day_start_ms(int(now.timestamp() * 1000))
    # 连续 48 根 1H，覆盖当天与前一天（前一天完整，因此两天都应落库）。
    hourly = [
        [str(day_now - 24 * 3_600_000 + index * 3_600_000), str(index)]
        for index in range(48)
    ]

    async def fetch(end: str | None) -> list[list[str]]:
        return hourly  # 一页不满 100 → 视为数据耗尽，停止分页

    stored: list[tuple[str, int, dict]] = []

    async def fake_store(metric, query_key, period, unit, ts_ms, payload) -> None:
        stored.append((period, ts_ms, payload))

    monkeypatch.setattr("okx_backend.services.m25_stats._store_stat", fake_store)
    monkeypatch.setattr("okx_backend.services.m25_stats._throttle", AsyncMock())

    async def no_existing(*args) -> set[int]:  # noqa: ANN002
        return set()

    monkeypatch.setattr("okx_backend.services.m25_stats._existing_daily_ts", no_existing)

    saved = await backfill_ny_day_metric(
        fetch, M25Metric.S01, "NVDA-USDT-SWAP", None,
        _s01_row_to_payload, ny_day_open, now=now,
    )

    assert saved == 2
    assert [period for period, _, _ in stored] == ["1D", "1D"]
    assert [ts for _, ts, _ in stored] == [day_now - 24 * 3_600_000, day_now]
    # 取的是日界那一根的官方读数，并标注派生来源。
    assert stored[1][2]["longShortAcctRatio"] == "24"
    assert stored[1][2]["srcPeriod"] == "1H"
    assert stored[1][2]["srcTs"] == str(day_now)


def test_missing_ny_days_covers_prior_days_in_window_and_excludes_today() -> None:
    from okx_backend.services.m25_stats import (
        M25_DAILY_KEEP_DAYS,
        m25_daily_cutoff_ms,
        missing_ny_days,
    )
    from okx_backend.services.ny_day import ny_day_start_days_ago

    now = datetime(2026, 11, 10, 18, tzinfo=UTC)  # 窗口跨过 11-01 夏令时结束
    all_missing = missing_ny_days(set(), now)
    assert M25_DAILY_KEEP_DAYS == 58
    assert len(all_missing) == 57
    assert all_missing[0] == m25_daily_cutoff_ms(now) == ny_day_start_days_ago(57, now)
    assert ny_day_start_days_ago(0, now) not in all_missing

    assert missing_ny_days(set(all_missing), now) == []
    present = set(all_missing) - {all_missing[3]}
    assert missing_ny_days(present, now) == [all_missing[3]]


@pytest.mark.asyncio
async def test_ny_day_backfill_skips_request_when_window_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from okx_backend.services.m25_stats import missing_ny_days

    now = datetime(2026, 9, 21, 18, tzinfo=UTC)
    complete = set(missing_ny_days(set(), now))

    async def existing(*args) -> set[int]:  # noqa: ANN002
        return complete

    fetch = AsyncMock()
    monkeypatch.setattr("okx_backend.services.m25_stats._existing_daily_ts", existing)

    saved = await backfill_ny_day_metric(
        fetch, M25Metric.S05, "BTC-USDT-SWAP", None,
        _s05_row_to_payload, ny_day_open, now=now,
    )
    assert saved == 0
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_ny_day_backfill_pages_back_only_to_oldest_missing_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from okx_backend.services.m25_stats import missing_ny_days

    now = datetime(2026, 9, 21, 18, tzinfo=UTC)
    days = missing_ny_days(set(), now)
    oldest_missing = days[-2]

    async def existing(*args) -> set[int]:  # noqa: ANN002
        return set(days) - {oldest_missing, days[-1]}

    ends: list[str | None] = []
    now_ms = int(now.timestamp() * 1000)

    async def fetch(end: str | None) -> list[list[str]]:
        ends.append(end)
        top = int(end) if end else now_ms
        return [[str(top - i * 3_600_000), "1.0"] for i in range(100)]

    monkeypatch.setattr("okx_backend.services.m25_stats._existing_daily_ts", existing)
    monkeypatch.setattr("okx_backend.services.m25_stats._throttle", AsyncMock())
    monkeypatch.setattr("okx_backend.services.m25_stats._store_stat", AsyncMock())

    await backfill_ny_day_metric(
        fetch, M25Metric.S01, "BTC-USDT-SWAP", None,
        _s01_row_to_payload, ny_day_open, now=now,
    )
    # 最早缺失日在 2 天前（约 62 小时）：100 根 1H 一页即可越过，不再翻页到窗口起点。
    assert ends == [None]


def test_m25_window_matches_official_1440_row_limit() -> None:
    from okx_backend.services.m25_stats import OKX_STAT_MAX_ROWS, m25_window_days

    assert OKX_STAT_MAX_ROWS == 1440
    assert m25_window_days("5m") == 5
    assert m25_window_days("15m") == 15
