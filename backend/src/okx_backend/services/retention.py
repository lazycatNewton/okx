"""7 天／80 根／10×24 小时滚动清理任务。

依据 okx-requirements.md「保存、保留与首次启动回填」：
- 产品目录、订阅目录、M22 当前目录/版本永久保存，不参与本清理。
- K 线（M02）：`1D` 只保留最新 80 根（按 `inst_id+kind+bar` 分组，不是全局 80 根）；
  `1m/5m/15m/30m` 保留最近 10×24 小时；`1s` 保留最近 7 天；`1H` 是纽约自然日日线的
  派生源（见 services/ny_day.py），保留窗口覆盖最近 80 个纽约自然日。
- M25：保留官方 1,440 条上限对应的时长——`5m` 5 天、`15m` 15 天、`1D` 58 个纽约自然日
  （见 services/m25_stats.py）。
- 其余频道（M01/M03/M05/M10/M13/M22 更新/M23/M25 除外）均为滚动 7×24 小时，
  以各自的业务时间戳为准。M01/M03/M05/M10/M13 自 2026-10-07 起暂停写入 MySQL，
  保留其清理只为让存量行自然过期。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from loguru import logger
from sqlalchemy import CursorResult, Select, delete, func, select
from sqlalchemy.orm import InstrumentedAttribute

from okx_backend.db.base import session_scope
from okx_backend.db.models import (
    Book5Snapshot,
    Candle,
    EconomicCalendarEvent,
    EventContractRevision,
    M25Stat,
    MarkPriceSnapshot,
    OpenInterestSnapshot,
    PublicTrade,
    TickerSnapshot,
)
from okx_backend.services.candle_policy import (
    DAILY_CANDLE_KEEP,
    MINUTE_BARS,
    candle_cutoff_ms,
    is_count_limited_bar,
)
from okx_backend.services.m25_stats import (
    NY_DAY_PERIOD,
    PERIODS_S01_S04_S05,
    m25_daily_cutoff_ms,
    m25_window_days,
)
from okx_backend.services.ny_day import NY_DAY_SOURCE_BAR

# (模型, 表名, 业务时间戳字段, 保留天数)：单条快照/事件按业务时间戳滚动 7 天清理。
# 表名单独列出而不是读 model.__tablename__，因为 mypy 对 DeclarativeBase 子类的
# __tablename__ 没有静态类型信息，读它会报 attr-defined；这里的表名只用于日志展示。
SIMPLE_RETENTION_TABLES: tuple[tuple[type, str, InstrumentedAttribute, int], ...] = (
    (TickerSnapshot, "m01_ticker_snapshots", TickerSnapshot.ts_ms, 7),
    (PublicTrade, "m03_public_trades", PublicTrade.ts_ms, 7),
    (Book5Snapshot, "m05_book5_snapshots", Book5Snapshot.ts_ms, 7),
    (MarkPriceSnapshot, "m10_mark_price_snapshots", MarkPriceSnapshot.ts_ms, 7),
    (OpenInterestSnapshot, "m13_open_interest_snapshots", OpenInterestSnapshot.ts_ms, 7),
    (EventContractRevision, "m22_revisions", EventContractRevision.business_ts, 7),
    (EconomicCalendarEvent, "m23_economic_calendar", EconomicCalendarEvent.ts_ms, 7),
)


def build_simple_cutoff_delete(
    model: type, column: InstrumentedAttribute, days: int, now: datetime
):
    """返回删除 `column < cutoff` 的 DELETE 语句；不执行，便于单元测试编译结果。"""

    cutoff_ms = int((now - timedelta(days=days)).timestamp() * 1000)
    return delete(model).where(column < cutoff_ms)


def build_m25_deletes(now: datetime) -> list[Any]:
    """M25 按周期各自的窗口清理：`5m`/`15m` 为 1,440 × 周期，`1D` 按纽约自然日。"""

    statements: list[Any] = []
    for period in PERIODS_S01_S04_S05:
        if period == NY_DAY_PERIOD:
            cutoff = m25_daily_cutoff_ms(now)
        else:
            cutoff = int((now - timedelta(days=m25_window_days(period))).timestamp() * 1000)
        statements.append(
            delete(M25Stat).where(M25Stat.period == period, M25Stat.ts_ms < cutoff)
        )
    return statements


def build_candle_age_delete(bar: str, now: datetime):
    """交易价格/标记价格 K 线中，按时长滚动保留的周期（1s/1m/5m/15m/30m，不含 1D）。"""

    if is_count_limited_bar(bar):
        return None
    cutoff = candle_cutoff_ms(bar, now)
    if cutoff is None:
        return None
    return delete(Candle).where(Candle.bar == bar, Candle.ts_ms < cutoff)


def build_daily_candle_cap_subquery(keep: int = DAILY_CANDLE_KEEP) -> Select:
    """`1D` K 线只保留最新 `keep` 根，按 `inst_id + kind` 分组（bar 已固定为 1D）。

    用 MySQL 8.0+ 窗口函数标出每组内按时间倒序的名次，取名次超过 keep 的行 id。
    """

    row_number = (
        func.row_number()
        .over(partition_by=(Candle.inst_id, Candle.kind), order_by=Candle.ts_ms.desc())
        .label("rn")
    )
    ranked = select(Candle.id, row_number).where(Candle.bar == "1D").subquery()
    return select(ranked.c.id).where(ranked.c.rn > keep)


# `1H` 是纽约日线的派生源，同样按时长清理（窗口见 candle_policy.candle_cutoff_ms）。
ALL_CANDLE_BARS_WITH_AGE_LIMIT = (*MINUTE_BARS, "1s", NY_DAY_SOURCE_BAR)


async def run_retention_cleanup(now: datetime | None = None) -> dict[str, int]:
    """执行一轮清理，返回各表本轮删除行数（用于日志/观测，不代表累计总量）。"""

    current = now or datetime.now(UTC)
    deleted: dict[str, int] = {}
    async with session_scope() as session:
        for model, table_name, column, days in SIMPLE_RETENTION_TABLES:
            stmt = build_simple_cutoff_delete(model, column, days, current)
            result = cast(CursorResult, await session.execute(stmt))
            deleted[table_name] = result.rowcount

        m25_total = 0
        for stmt in build_m25_deletes(current):
            result = cast(CursorResult, await session.execute(stmt))
            m25_total += result.rowcount
        deleted["m25_stats"] = m25_total

        candle_age_total = 0
        for bar in ALL_CANDLE_BARS_WITH_AGE_LIMIT:
            stmt = build_candle_age_delete(bar, current)
            if stmt is None:
                continue
            result = cast(CursorResult, await session.execute(stmt))
            candle_age_total += result.rowcount
        deleted["candles_age_limited"] = candle_age_total

        stale_ids = build_daily_candle_cap_subquery()
        cap_stmt = delete(Candle).where(Candle.id.in_(stale_ids))
        result = cast(CursorResult, await session.execute(cap_stmt))
        deleted["candles_daily_cap"] = result.rowcount

    logger.info(f"retention cleanup done: {deleted}")
    return deleted


async def run_retention_cleanup_forever(interval_seconds: float = 3600.0) -> None:
    """后台常驻任务：每 `interval_seconds` 跑一轮清理；单轮失败记录日志后继续下一轮，
    不能因一次数据库瞬时故障就让清理永久停摆。"""

    while True:
        try:
            await run_retention_cleanup()
        except Exception as exc:  # noqa: BLE001 - 清理失败不应影响采集/服务可用性
            logger.error(f"retention cleanup failed: {exc!r}")
        await asyncio.sleep(interval_seconds)
