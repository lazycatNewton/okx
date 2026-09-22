"""M25 统计与历史（S01/S04/S05）。

依据 okx-requirements.md「M25 补充数据」及「保存、保留与首次启动回填」：
- S01/S04/S05：按 `instId`，周期 `5m/15m/1D`。其中 `1D` 不使用 OKX 的 `1D`（UTC+8 开盘
  口径）或 `1Dutc`（UTC+0 口径），而是请求官方 `1H` 后在后端按纽约自然日重采样，
  与全系统统一的纽约时间展示对齐（见 services/ny_day.py）。
- 所有历史保留 7 天。
- 启动回填之后，S01/S04/S05 在各自周期结束后请求对应周期；短暂请求失败保留最近有效数据，
  下一个计划周期重试，不伪造新记录。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy.dialects.mysql import insert as mysql_insert

from okx_backend.db.base import session_scope
from okx_backend.db.models import M25Metric, M25Stat
from okx_backend.okx_client.rest import OkxRestClient
from okx_backend.services.ny_day import (
    NY_DAY_SOURCE_BAR,
    decimal_sum,
    group_by_ny_day,
)

# S01/S04/S05 共享周期。
PERIODS_S01_S04_S05: tuple[str, ...] = ("5m", "15m", "1D")
S04_UNITS: tuple[str, ...] = ("0", "1", "2")

_PERIOD_SECONDS = {"5m": 300.0, "15m": 900.0, "1H": 3600.0, "1D": 86400.0}

# 全局请求节流：多个 (instId, period, unit) 组合的回填任务通过 asyncio.gather 并发调度，
# 若不加限制，同一进程内针对同一端点的首个分页请求会在同一时刻集中发出（例如 S04 单个
# instId 就有 3 周期 x 3 单位 = 9 个并发首请求），瞬间超过 OKX 最严的 5 次/2s 限速并
# 触发 429。这里用一把跨所有 M25 请求共享的锁，强制任意两次实际 REST 调用之间至少间隔
# `_GLOBAL_MIN_INTERVAL_SECONDS`；按最严限速 5 次/2s=2.5 次/s 留出安全余量，改为全局
# 2 次/s，足够覆盖 S01/S04（5 次/2s）与 S05（10 次/2s）各自的限速规则。
_GLOBAL_MIN_INTERVAL_SECONDS = 0.5
_global_rate_lock = asyncio.Lock()
_global_last_request_at = 0.0


async def _throttle() -> None:
    """在每次实际发起 REST 请求前调用，确保跨所有并发任务的全局请求间隔。"""

    global _global_last_request_at
    async with _global_rate_lock:
        now = asyncio.get_event_loop().time()
        wait = _global_last_request_at + _GLOBAL_MIN_INTERVAL_SECONDS - now
        if wait > 0:
            await asyncio.sleep(wait)
        _global_last_request_at = asyncio.get_event_loop().time()


# 本产品对外的日粒度。OKX 的 `1D` 是 UTC+8 开盘口径、`1Dutc` 是 UTC+0 口径，都不是
# 纽约自然日；统一改为请求官方 `1H`，在后端按 America/New_York 自然日重采样。
NY_DAY_PERIOD = "1D"


def source_period(period: str) -> str:
    """返回实际向 OKX 请求的粒度：`1D` 走派生源 `1H`，其余原样。"""

    return NY_DAY_SOURCE_BAR if period == NY_DAY_PERIOD else period


def period_seconds(period: str) -> float:
    return _PERIOD_SECONDS[period]


def poll_interval_seconds(period: str) -> float:
    """轮询间隔按实际请求的源粒度算：派生的 `1D` 每小时拉一次 1H，持续修正当天的日线。"""

    return _PERIOD_SECONDS[source_period(period)]


# 每次 `1D` 轮询回看的 1H 根数：48 根保证完整覆盖当前纽约自然日与前一个自然日，
# 即使轮询因重启/请求失败错过了几个小时，也能把整天重新补齐而不是留下缺口。
NY_DAY_POLL_LOOKBACK_HOURS = 48


def resample_ny_day(
    hourly: list[tuple[int, dict[str, Any]]], aggregate: Any
) -> list[tuple[int, dict[str, Any]]]:
    """把 `(ts_ms, payload)` 的 1H 序列按纽约自然日聚合，返回 `(日界 ts_ms, payload)`。

    `aggregate` 返回 `None` 表示该自然日的源数据不足以派生日线（见 `_has_day_open`），
    这样的日子直接跳过，不写入残缺值。
    """

    grouped = group_by_ny_day(hourly)
    result: list[tuple[int, dict[str, Any]]] = []
    for day in sorted(grouped):
        payload = aggregate(day, grouped[day])
        if payload is not None:
            result.append((day, payload))
    return result


def _has_day_open(day_start_ms: int, rows: list[tuple[int, dict[str, Any]]]) -> bool:
    """本次拉到的 1H 是否真的覆盖到这个纽约自然日的日界那一根。

    分页窗口的最老一天通常只拉到半天，此时既不能把当天中途的读数当成日界读数，也不能
    把半天的量当成全天累计；这种日子一律跳过，等下一次覆盖完整时再写。纽约 00:00 在
    EDT/EST 下分别是 UTC 04:00／05:00，都正好落在整点上，因此日界那一根的时间戳与
    `day_start_ms` 精确相等，不需要容差。
    """

    return bool(rows) and rows[0][0] == day_start_ms


def ny_day_open(
    day_start_ms: int, rows: list[tuple[int, dict[str, Any]]]
) -> dict[str, Any] | None:
    """快照型指标（S01 多空人数比、S05 持仓量）的日线取值。

    这些量不可求和，取当日**日界时刻**的读数，与 OKX 自身“开盘价 k 线”的取值语义一致。
    """

    if not _has_day_open(day_start_ms, rows):
        return None
    src_ts, payload = rows[0]
    derived = dict(payload)
    derived["ts"] = str(day_start_ms)
    derived["srcPeriod"] = NY_DAY_SOURCE_BAR
    derived["srcTs"] = str(src_ts)
    return derived


def ny_day_taker_volume_sum(
    day_start_ms: int, rows: list[tuple[int, dict[str, Any]]]
) -> dict[str, Any] | None:
    """S04 主动买卖量是区间累计量，日线必须按纽约自然日**求和**，不能取日界单根读数。

    当天尚未结束时得到的是“截至此刻的累计量”，下一次轮询会用更完整的和覆盖同一行。
    """

    if not _has_day_open(day_start_ms, rows):
        return None
    return {
        "ts": str(day_start_ms),
        "sellVol": decimal_sum(payload.get("sellVol") for _, payload in rows),
        "buyVol": decimal_sum(payload.get("buyVol") for _, payload in rows),
        "srcPeriod": NY_DAY_SOURCE_BAR,
        "srcHours": str(len(rows)),
    }


async def _store_stat(
    metric: M25Metric, query_key: str, period: str | None, unit: str | None,
    ts_ms: int, raw_payload: dict[str, Any],
) -> None:
    """`period`/`unit` 为 `None` 时按 `''` 存储（唯一索引去重需要非 NULL，见 M25Stat 注释）。"""

    async with session_scope() as session:
        stmt = mysql_insert(M25Stat).values(
            metric=metric, query_key=query_key, period=period or "", unit=unit or "",
            ts_ms=ts_ms, raw_payload=raw_payload,
        ).on_duplicate_key_update(raw_payload=raw_payload)
        await session.execute(stmt)


def _cutoff_ms(days: float, now: datetime) -> int:
    return int((now - timedelta(days=days)).timestamp() * 1000)


# -- S01/S04/S05：[ts, ...] 数组行，按 end 递减分页 ---------------------------
async def _collect_array_rows(
    fetch: Any, row_to_payload: Any, cutoff: int
) -> list[tuple[int, dict[str, Any]]]:
    """按 `end` 递减分页拉取，直到越过 `cutoff` 或页不满（数据耗尽）；返回解析后的行。"""

    end: str | None = None
    collected: list[tuple[int, dict[str, Any]]] = []
    while True:
        await _throttle()
        rows = await fetch(end=end)
        if not rows:
            return collected
        parsed = [row_to_payload(row) for row in rows]
        collected.extend(parsed)
        oldest = min(ts_ms for ts_ms, _ in parsed)
        if oldest <= cutoff or len(rows) < 100:
            return collected
        end = str(oldest - 1)


async def backfill_array_metric(
    fetch: Any,
    metric: M25Metric,
    query_key: str,
    period: str,
    unit: str | None,
    row_to_payload: Any,
    cutoff_days: float,
    now: datetime | None = None,
) -> int:
    """`fetch(end=...) -> list[list[str]]`；按 `row_to_payload(row) -> (ts_ms, payload)` 解析。

    返回本次实际写入的行数（用于测试与观测，不代表累计总量）。
    """

    cutoff = _cutoff_ms(cutoff_days, now or datetime.now(UTC))
    saved = 0
    for ts_ms, payload in await _collect_array_rows(fetch, row_to_payload, cutoff):
        await _store_stat(metric, query_key, period, unit, ts_ms, payload)
        saved += 1
    return saved


async def backfill_ny_day_metric(
    fetch: Any,
    metric: M25Metric,
    query_key: str,
    unit: str | None,
    row_to_payload: Any,
    aggregate: Any,
    cutoff_days: float,
    now: datetime | None = None,
) -> int:
    """`1D` 专用：`fetch` 请求的是官方 `1H`，落库前按纽约自然日重采样成日线。

    存储的 `period` 仍是 `1D`（查询接口与前端口径不变），但 payload 里会带上
    `srcPeriod`/`srcTs` 标注派生来源，保留“可追溯到官方返回值”的要求。
    """

    cutoff = _cutoff_ms(cutoff_days, now or datetime.now(UTC))
    hourly = await _collect_array_rows(fetch, row_to_payload, cutoff)
    saved = 0
    for day_start_ms, payload in resample_ny_day(hourly, aggregate):
        await _store_stat(metric, query_key, NY_DAY_PERIOD, unit, day_start_ms, payload)
        saved += 1
    return saved


def _s01_row_to_payload(row: list[str]) -> tuple[int, dict[str, Any]]:
    ts, ratio = row
    return int(ts), {"ts": ts, "longShortAcctRatio": ratio}


def _s04_row_to_payload(row: list[str]) -> tuple[int, dict[str, Any]]:
    ts, sell_vol, buy_vol = row
    return int(ts), {"ts": ts, "sellVol": sell_vol, "buyVol": buy_vol}


def _s05_row_to_payload(row: list[str]) -> tuple[int, dict[str, Any]]:
    ts, oi, oi_ccy, oi_usd = row
    return int(ts), {"ts": ts, "oi": oi, "oiCcy": oi_ccy, "oiUsd": oi_usd}


def _array_backfill_job(
    fetch: Any,
    metric: M25Metric,
    query_key: str,
    period: str,
    unit: str | None,
    row_to_payload: Any,
    aggregate: Any,
    cutoff_days: float,
) -> Any:
    """`period == "1D"` 时把官方 1H 重采样成纽约自然日，否则按原周期逐行落库。"""

    if period == NY_DAY_PERIOD:
        return backfill_ny_day_metric(
            fetch, metric, query_key, unit, row_to_payload, aggregate, cutoff_days,
        )
    return backfill_array_metric(
        fetch, metric, query_key, period, unit, row_to_payload, cutoff_days,
    )


async def backfill_m25(products: list[tuple[str, str]]) -> None:
    """为已选 live 永续产品回填 M25 历史；不阻塞实时采集，重复键由 upsert 覆盖。

    `products`：[(instId, instType), ...]，只处理 instType == SWAP（M25 仅适用永续）。
    单个 (指标, 产品, 周期) 组合失败不应让其余已选产品/指标的回填全部落空；
    因此用 `return_exceptions=True` 隔离故障，仅记录日志。
    """

    swap_products = [inst_id for inst_id, inst_type in products if inst_type == "SWAP"]
    if not swap_products:
        return

    async with OkxRestClient() as client:
        jobs: list[tuple[str, Any]] = []
        for inst_id in swap_products:
            for period in PERIODS_S01_S04_S05:
                jobs.append(
                    (
                        f"S01 {inst_id} {period}",
                        _array_backfill_job(
                            _s01_fetch(client, inst_id, period),
                            M25Metric.S01, inst_id, period, None, _s01_row_to_payload,
                            ny_day_open, 7,
                        ),
                    )
                )
                jobs.append(
                    (
                        f"S05 {inst_id} {period}",
                        _array_backfill_job(
                            _s05_fetch(client, inst_id, period),
                            M25Metric.S05, inst_id, period, None, _s05_row_to_payload,
                            ny_day_open, 7,
                        ),
                    )
                )
                for unit in S04_UNITS:
                    jobs.append(
                        (
                            f"S04 {inst_id} {period} unit={unit}",
                            _array_backfill_job(
                                _s04_fetch(client, inst_id, period, unit),
                                M25Metric.S04, inst_id, period, unit, _s04_row_to_payload,
                                ny_day_taker_volume_sum, 7,
                            ),
                        )
                    )
        results = await asyncio.gather(*(job for _, job in jobs), return_exceptions=True)
        for (label, _), result in zip(jobs, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(f"m25 backfill job failed, skipped: {label}: {result!r}")


def _s01_fetch(client: OkxRestClient, inst_id: str, period: str) -> Any:
    src = source_period(period)
    return lambda end: client.get_long_short_account_ratio_contract(inst_id, period=src, end=end)


def _s05_fetch(client: OkxRestClient, inst_id: str, period: str) -> Any:
    src = source_period(period)
    return lambda end: client.get_open_interest_history(inst_id, period=src, end=end)


def _s04_fetch(client: OkxRestClient, inst_id: str, period: str, unit: str) -> Any:
    src = source_period(period)
    return lambda end: client.get_taker_volume_contract(inst_id, period=src, unit=unit, end=end)


# -- 持续轮询：启动回填之后，各周期结束后请求对应周期 -------------------------
async def _poll_forever(fetch: Any, store_rows: Any, interval_seconds: float) -> None:
    """`store_rows` 接收整批返回行，而不是逐行——派生的 `1D` 需要整批才能按日重采样。"""

    while True:
        try:
            await _throttle()
            rows = await fetch()
            if rows:
                await store_rows(rows)
        except Exception as exc:  # noqa: BLE001 - 单次失败保留最近有效数据，下一周期重试
            logger.warning(f"m25 poll failed: {exc!r}")
        await asyncio.sleep(interval_seconds)


def _array_store_rows(
    metric: M25Metric,
    query_key: str,
    period: str,
    unit: str | None,
    row_to_payload: Any,
    aggregate: Any,
) -> Any:
    """构造轮询用的批量落库函数：`1D` 先按纽约自然日重采样，其余周期逐行直存。"""

    async def store_rows(rows: list[list[str]]) -> None:
        parsed = [row_to_payload(row) for row in rows]
        if period == NY_DAY_PERIOD:
            for day_start_ms, payload in resample_ny_day(parsed, aggregate):
                await _store_stat(metric, query_key, NY_DAY_PERIOD, unit, day_start_ms, payload)
            return
        for ts_ms, payload in parsed:
            await _store_stat(metric, query_key, period, unit, ts_ms, payload)

    return store_rows


def _poll_limit(period: str) -> int:
    """派生的 `1D` 每次要回看 48 根 1H 才能覆盖完整的纽约自然日；其余周期取最近 5 根即可。"""

    return NY_DAY_POLL_LOOKBACK_HOURS if period == NY_DAY_PERIOD else 5


async def start_m25_polling(
    products: list[tuple[str, str]],
) -> tuple[list[asyncio.Task], OkxRestClient]:
    """为每个已选 live 永续产品 / 关联币种启动持续轮询任务。

    返回 `(tasks, client)`；调用方负责在停止全部 tasks 后 `await client.aclose()`，
    否则底层 httpx.AsyncClient 连接不会被释放。

    `1D` 的轮询请求的是官方 `1H`（每小时一次、回看 48 根），落库前按纽约自然日重采样；
    其余周期仍按自身周期结束后请求最近 5 根。
    """

    swap_products = [inst_id for inst_id, inst_type in products if inst_type == "SWAP"]
    tasks: list[asyncio.Task] = []
    client = OkxRestClient()
    if not swap_products:
        return tasks, client

    for inst_id in swap_products:
        for period in PERIODS_S01_S04_S05:
            src = source_period(period)
            limit = _poll_limit(period)
            tasks.append(
                asyncio.create_task(
                    _poll_forever(
                        lambda i=inst_id, sp=src, n=limit: (
                            client.get_long_short_account_ratio_contract(i, period=sp, limit=n)
                        ),
                        _array_store_rows(
                            M25Metric.S01, inst_id, period, None,
                            _s01_row_to_payload, ny_day_open,
                        ),
                        poll_interval_seconds(period),
                    )
                )
            )
            tasks.append(
                asyncio.create_task(
                    _poll_forever(
                        lambda i=inst_id, sp=src, n=limit: (
                            client.get_open_interest_history(i, period=sp, limit=n)
                        ),
                        _array_store_rows(
                            M25Metric.S05, inst_id, period, None,
                            _s05_row_to_payload, ny_day_open,
                        ),
                        poll_interval_seconds(period),
                    )
                )
            )
            for unit in S04_UNITS:
                tasks.append(
                    asyncio.create_task(
                        _poll_forever(
                            lambda i=inst_id, sp=src, u=unit, n=limit: (
                                client.get_taker_volume_contract(i, period=sp, unit=u, limit=n)
                            ),
                            _array_store_rows(
                                M25Metric.S04, inst_id, period, unit,
                                _s04_row_to_payload, ny_day_taker_volume_sum,
                            ),
                            poll_interval_seconds(period),
                        )
                    )
                )

    return tasks, client
