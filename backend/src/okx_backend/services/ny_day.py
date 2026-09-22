"""纽约自然日（America/New_York）分桶与重采样工具。

为什么需要它：OKX 的日粒度只有两种口径——`1D` 是 **UTC+8 开盘价 K 线**（见
`okx-v5-api` Skill 的 `historyCandles.md`、`longShortAccountRatioContract.md`、
`openInestVolumeHistory.md`、`contractTakerVolume.md`），`1Dutc` 是 UTC+0 口径；
两者都不是纽约自然日。本产品统一以纽约时间展示（见 `frontend/src/time.ts`），
因此所有日粒度序列都改为：向 OKX 请求官方 `1H` 粒度，在后端按 America/New_York
自然日重采样得到 `1D`。夏令时切换（EST/EDT）由 `zoneinfo` 自动处理，纽约 00:00
在 EDT 对应 UTC 04:00、在 EST 对应 UTC 05:00，两者都落在整点上，所以 `1H` 源粒度
足以精确对齐日界，不需要更细的粒度。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

NY_TIME_ZONE = ZoneInfo("America/New_York")

# 派生日线所使用的官方源粒度；REST `bar`/`period` 与 WS 频道名都用它。
NY_DAY_SOURCE_BAR = "1H"
SOURCE_BAR_SECONDS = 3600


def ny_day_start_ms(ts_ms: int) -> int:
    """返回 `ts_ms` 所属纽约自然日 00:00 的 UTC 毫秒时间戳。

    纽约的夏令时切换发生在凌晨 2 点，00:00 始终存在且不重复，因此 `replace(hour=0)`
    不会落在不存在或歧义的墙上时间里。
    """

    local = datetime.fromtimestamp(ts_ms / 1000, tz=NY_TIME_ZONE)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 1000)


def ny_day_start_days_ago(days: int, now: datetime | None = None) -> int:
    """返回“今天（纽约）往前第 `days` 天”的纽约 00:00 对应 UTC 毫秒时间戳。

    aware datetime 的 `timedelta` 运算按墙上时间进行，正是这里需要的语义：无论中途
    是否跨过夏令时切换，往前 N 天始终落在当地 00:00。
    """

    local = (now or datetime.now(UTC)).astimezone(NY_TIME_ZONE)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - timedelta(days=days)).timestamp() * 1000)


def next_ny_day_start_ms(day_start_ms: int) -> int:
    """给定某个纽约自然日的 00:00，返回下一个自然日的 00:00（含夏令时修正）。"""

    local = datetime.fromtimestamp(day_start_ms / 1000, tz=NY_TIME_ZONE)
    following = (local + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(following.timestamp() * 1000)


def group_by_ny_day(rows: Iterable[tuple[int, dict]]) -> dict[int, list[tuple[int, dict]]]:
    """把 `(ts_ms, payload)` 序列按纽约自然日分组，组内按 `ts_ms` 升序。"""

    grouped: dict[int, list[tuple[int, dict]]] = {}
    for ts_ms, payload in rows:
        grouped.setdefault(ny_day_start_ms(ts_ms), []).append((ts_ms, payload))
    for bucket in grouped.values():
        bucket.sort(key=lambda item: item[0])
    return grouped


def decimal_sum(values: Iterable[str | None]) -> str | None:
    """求和成交量类字段；全为 None 时返回 None。"""

    total = Decimal(0)
    seen = False
    for value in values:
        if value is None or value == "":
            continue
        total += Decimal(value)
        seen = True
    if not seen:
        return None
    # 固定小数表示：`str(Decimal)` 对极小/极大值会输出科学计数法，前端按字符串解析会失真。
    return format(total, "f")
