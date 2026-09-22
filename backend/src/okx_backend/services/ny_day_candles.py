"""由官方 `1H` K 线派生纽约自然日 `1D` K 线（M02 成交价 / M11 标记价格）。

OKX 的 `1D` 是 UTC+8 开盘价口径、`1Dutc` 是 UTC+0 口径，都不是纽约自然日（见
`ny_day.py` 的说明）。本模块把已入库的官方 `1H` 行按 America/New_York 自然日聚合：
`o` 取当日首根 1H 的开盘、`h`/`l` 取当日极值、`c` 取当日末根 1H 的收盘、
`vol`/`volCcy`/`volCcyQuote` 按日求和；当日若尚未结束则 `confirm="0"`。

派生结果写回 `candles` 表的 `bar="1D"`，因此查询接口、前端图表、80 根保留策略都不用
改口径；`1H` 行本身作为派生源常驻（保留窗口见 `candle_policy.candle_cutoff_ms`）。
每次收到新的 1H 推送都从数据库重算受影响的那一天，而不是在内存里增量累加——重算的
代价是一天最多 24 行，换来的是进程重启、WS 重连、乱序推送后都能自愈。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from okx_backend.db.base import session_scope
from okx_backend.db.models import Candle, CandleKind
from okx_backend.services.candle_cache import cache_latest_candle
from okx_backend.services.candle_policy import DAILY_CANDLE_KEEP
from okx_backend.services.ny_day import (
    NY_DAY_SOURCE_BAR,
    decimal_sum,
    group_by_ny_day,
    next_ny_day_start_ms,
    ny_day_start_days_ago,
    ny_day_start_ms,
)


def _redis_prefix(kind: CandleKind) -> str:
    return "m02" if kind == CandleKind.TRADE else "m11"


def aggregate_ny_day(
    day_start_ms: int, rows: list[dict], now_ms: int
) -> dict[str, str | None] | None:
    """把某个纽约自然日内按时间升序的 1H 行聚合成一根日线。

    `rows` 的每一项是 `{"ts","o","h","l","c","vol","volCcy","volCcyQuote"}`。
    """

    if not rows:
        return None
    rows = sorted(rows, key=lambda row: int(row["ts"]))
    timestamps = [int(row["ts"]) for row in rows]
    day_end = next_ny_day_start_ms(day_start_ms)
    if timestamps[0] != day_start_ms or timestamps[-1] >= day_end:
        return None
    if any(right - left != 3_600_000
           for left, right in zip(timestamps, timestamps[1:], strict=False)):
        return None
    ended = day_end <= now_ms
    if ended and timestamps[-1] + 3_600_000 != day_end:
        return None
    highs = [Decimal(row["h"]) for row in rows]
    lows = [Decimal(row["l"]) for row in rows]
    complete = ended and all(row.get("confirm") == "1" for row in rows)
    return {
        "ts": str(day_start_ms),
        "o": rows[0]["o"],
        "h": format(max(highs), "f"),
        "l": format(min(lows), "f"),
        "c": rows[-1]["c"],
        "vol": decimal_sum(row.get("vol") for row in rows),
        "volCcy": decimal_sum(row.get("volCcy") for row in rows),
        "volCcyQuote": decimal_sum(row.get("volCcyQuote") for row in rows),
        # 经过午夜不代表数据完整：必须包含全部 23/24/25 根已闭合小时线才能确认。
        "confirm": "1" if complete else "0",
    }


async def _load_source_rows(
    inst_id: str, kind: CandleKind, since_ms: int
) -> list[tuple[int, dict]]:
    async with session_scope() as session:
        rows = await session.scalars(
            select(Candle)
            .where(
                Candle.inst_id == inst_id,
                Candle.kind == kind,
                Candle.bar == NY_DAY_SOURCE_BAR,
                Candle.ts_ms >= since_ms,
            )
            .order_by(Candle.ts_ms.asc())
        )
        return [
            (
                row.ts_ms,
                {
                    "ts": str(row.ts_ms), "o": row.o, "h": row.h, "l": row.low, "c": row.c,
                    "vol": row.vol, "volCcy": row.vol_ccy, "volCcyQuote": row.vol_ccy_quote,
                    "confirm": row.confirm,
                },
            )
            for row in rows.all()
        ]


async def rebuild_ny_day_candles(
    inst_id: str,
    kind: CandleKind,
    only_day_start_ms: int | None = None,
    now: datetime | None = None,
) -> list[dict[str, str | None]]:
    """按纽约自然日重算 `1D` 并 upsert，返回本次写入的日线（按时间升序）。

    `only_day_start_ms` 给出时只重算那一天（实时 1H 推送路径用），否则重算保留窗口内的
    全部自然日（回填完成后用）。
    """

    current = now or datetime.now(UTC)
    now_ms = int(current.timestamp() * 1000)
    window_start = ny_day_start_days_ago(DAILY_CANDLE_KEEP - 1, current)
    since = max(window_start, only_day_start_ms) if only_day_start_ms else window_start

    grouped = group_by_ny_day(await _load_source_rows(inst_id, kind, since))
    if only_day_start_ms is not None:
        grouped = {k: v for k, v in grouped.items() if k == only_day_start_ms}

    daily: list[dict[str, str | None]] = []
    for day_start in sorted(grouped):
        if day_start < window_start:
            continue
        candle = aggregate_ny_day(day_start, [p for _, p in grouped[day_start]], now_ms)
        if candle is not None:
            daily.append(candle)

    if not daily:
        return []

    async with session_scope() as session:
        for candle in daily:
            updates = dict(
                o=candle["o"], h=candle["h"], l=candle["l"], c=candle["c"], vol=candle["vol"],
                vol_ccy=candle["volCcy"], vol_ccy_quote=candle["volCcyQuote"],
                received_at=datetime.now(UTC), confirm=candle["confirm"],
            )
            guarded = [
                (name, case((Candle.confirm != "1", value), else_=Candle.__table__.c[name]))
                if candle["confirm"] != "1" else (name, value)
                for name, value in updates.items()
            ]
            # `values()` 用 ORM 属性名（`low`），`on_duplicate_key_update()` 用列名（`l`），
            # 与 market_collector._store_candle 保持一致。
            stmt = mysql_insert(Candle).values(
                inst_id=inst_id, kind=kind, bar="1D", ts_ms=int(str(candle["ts"])),
                o=candle["o"], h=candle["h"], low=candle["l"], c=candle["c"],
                vol=candle["vol"], vol_ccy=candle["volCcy"],
                vol_ccy_quote=candle["volCcyQuote"], confirm=candle["confirm"],
            ).on_duplicate_key_update(guarded)
            await session.execute(stmt)

    latest = daily[-1]
    await cache_latest_candle(f"{_redis_prefix(kind)}:latest:{inst_id}:1D", latest)
    return daily


async def on_source_candle_stored(inst_id: str, kind: CandleKind, ts_ms: int) -> dict | None:
    """实时/回填写入一根 1H 后调用：只重算它所属的纽约自然日，返回该日线。"""

    daily = await rebuild_ny_day_candles(inst_id, kind, only_day_start_ms=ny_day_start_ms(ts_ms))
    return daily[-1] if daily else None
