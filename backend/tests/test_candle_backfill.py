import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from okx_backend.collector.market_collector import MARK_SOURCE_BARS, TRADE_SOURCE_BARS
from okx_backend.db.models import CandleKind
from okx_backend.services import candle_backfill as module
from okx_backend.services.candle_backfill import _backfill_one, backfill_candles, backfill_plan
from okx_backend.services.ny_day import ny_day_start_days_ago


def test_backfill_prioritizes_chart_windows_before_second_bars() -> None:
    assert backfill_plan(("1s", "1m", "5m", "15m", "30m", "1H")) == (
        "1H", "30m", "15m", "5m", "1m", "1s"
    )


def test_source_bars_replace_daily_with_its_derivation_source() -> None:
    """对外仍是 1D，但向 OKX 订阅/回填的是 1H：OKX 的 1D 是 UTC+8 口径，不对齐纽约。"""

    assert TRADE_SOURCE_BARS == ("1s", "1m", "5m", "15m", "30m", "1H")
    assert MARK_SOURCE_BARS == ("1m", "5m", "15m", "30m", "1H")


@pytest.mark.asyncio
async def test_daily_bar_cannot_be_backfilled_directly() -> None:
    """`candle_cutoff_ms("1D")` 是 None，若误走分页循环会永远翻页，必须显式拒绝。"""

    with pytest.raises(ValueError, match="派生"):
        await _backfill_one(
            AsyncMock(), AsyncMock(), "NEW-USDT", CandleKind.TRADE, "1D"
        )


@pytest.mark.asyncio
async def test_hourly_backfill_covers_the_full_80_new_york_day_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1H 源必须一直翻页到第 80 个纽约自然日的 00:00，否则最早的日线无法派生。"""

    now = datetime.now(UTC)
    window_start = ny_day_start_days_ago(79, now)
    oldest_requested: list[int] = []

    class FakeClient:
        async def get_history_candles(
            self, inst_id: str, bar: str, *, after: str | None, limit: int, adjust: str
        ) -> list[list[str]]:
            end_ms = int(after) if after else int(now.timestamp() * 1000)
            rows = [
                [str(end_ms - (index + 1) * 3_600_000), "1", "2", "0", "1", "1", "1", "1", "1"]
                for index in range(limit)
            ]
            oldest_requested.append(min(int(row[0]) for row in rows))
            return rows

    rebuilt: list[tuple[str, CandleKind]] = []

    async def fake_rebuild(inst_id: str, kind: CandleKind) -> list[dict]:
        rebuilt.append((inst_id, kind))
        return []

    monkeypatch.setattr(
        "okx_backend.services.candle_backfill.rebuild_ny_day_candles", fake_rebuild
    )
    collector = AsyncMock()

    await _backfill_one(
        FakeClient(),  # type: ignore[arg-type]
        collector,
        "NEW-USDT",
        CandleKind.TRADE,
        "1H",
    )

    assert oldest_requested[-1] <= window_start
    # 回填期间不做逐根派生，整轮结束后统一重算一次整个窗口。
    assert all(call.kwargs["derive_ny_day"] is False
               for call in collector._store_candle.await_args_list)
    assert rebuilt == [("NEW-USDT", CandleKind.TRADE)]


@pytest.mark.asyncio
async def test_failed_hourly_history_does_not_prevent_minute_history(monkeypatch):
    """当前多个产品分钟线缺口一致：大周期任务失败不能使后续周期永远不执行。"""
    minute_started = asyncio.Event()

    async def fake_backfill(client, collector, inst_id, kind, bar, **kwargs):
        if bar == "1H":
            raise RuntimeError("transient upstream failure")
        if bar == "5m":
            minute_started.set()

    monkeypatch.setattr("okx_backend.services.candle_backfill._backfill_one", fake_backfill)
    monkeypatch.setattr("okx_backend.services.candle_backfill.OkxRestClient", AsyncMock)
    task = asyncio.create_task(backfill_candles([("NVDA-USDT-SWAP", "SWAP")], AsyncMock()))
    try:
        await asyncio.wait_for(minute_started.wait(), timeout=0.5)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_recent_reconciliation_keeps_failed_window_and_cancels_cleanly(monkeypatch):
    cutoffs = []
    sleeps = 0

    class Clock:
        ticks = 0

        @classmethod
        def now(cls, tz):
            cls.ticks += 1
            return datetime(2026, 9, 22, tzinfo=UTC) + timedelta(minutes=cls.ticks)

    async def backfill(*args, since_ms):
        cutoffs.append(since_ms)
        if len(cutoffs) == 1:
            raise ConnectionError("offline")

    async def sleep(seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(module, "_backfill_one", backfill)
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await module._reconcile_recent(AsyncMock(), AsyncMock(), "TEST", CandleKind.TRADE, "5m")
    assert cutoffs[1] == cutoffs[0]  # 失败不推进下界，断线窗口不会被跳过。
    assert cutoffs[2] > cutoffs[1]  # 成功之后才转为近期重叠窗口。


@pytest.mark.asyncio
async def test_full_backfill_retries_instead_of_abandoning_the_period(monkeypatch):
    backfill = AsyncMock(side_effect=[ConnectionError("offline"), None])
    sleep = AsyncMock()
    monkeypatch.setattr(module, "_backfill_one", backfill)
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    await module._retry_full_history(AsyncMock(), AsyncMock(), "TEST", CandleKind.TRADE, "5m")
    assert backfill.await_count == 2
    sleep.assert_awaited_once_with(30)
