"""K 线周期的存储保留策略。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from okx_backend.services.ny_day import NY_DAY_SOURCE_BAR, ny_day_start_days_ago

MINUTE_BARS = frozenset({"1m", "5m", "15m", "30m"})

# `1D` 只保留最新 80 根（需求：按 inst_id+kind 分组，不是全局 80 根）。
DAILY_CANDLE_KEEP = 80


def is_count_limited_bar(bar: str) -> bool:
    """日线只保留最近 80 根，不能用固定时长替代。"""

    return bar == "1D"


def is_ny_day_source_bar(bar: str) -> bool:
    """`1H` 不对外展示，只作为纽约自然日日线的派生源（见 services/ny_day.py）。"""

    return bar == NY_DAY_SOURCE_BAR


def candle_cutoff_ms(bar: str, now: datetime | None = None) -> int | None:
    """返回按业务时间戳清理的下界；日线由条数清理，故无时间下界。"""

    if is_count_limited_bar(bar):
        return None
    current = now or datetime.now(UTC)
    if is_ny_day_source_bar(bar):
        # 派生源的保留窗口刚好覆盖要展示的 80 个纽约自然日：早于第 80 天 00:00 的
        # 小时线对日线已无贡献，继续留着只会让表无意义地增长。
        return ny_day_start_days_ago(DAILY_CANDLE_KEEP - 1, current)
    retention = timedelta(days=10 if bar in MINUTE_BARS else 7)
    return int((current - retention).timestamp() * 1000)
