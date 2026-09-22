"""启动后在后台补齐 K 线历史，不阻塞实时 WS 采集。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from weakref import WeakKeyDictionary

from loguru import logger

from okx_backend.collector.market_collector import (
    MARK_SOURCE_BARS,
    TRADE_SOURCE_BARS,
    MarketCollector,
)
from okx_backend.db.models import CandleKind
from okx_backend.okx_client.rest import OkxRestClient
from okx_backend.services.candle_policy import candle_cutoff_ms, is_count_limited_bar
from okx_backend.services.ny_day import NY_DAY_SOURCE_BAR
from okx_backend.services.ny_day_candles import rebuild_ny_day_candles

# 所有产品/周期共享请求节流；不能每个任务各 sleep 0.11s 后一起冲击同一个 IP 限额。
# 按事件循环隔离，避免测试/应用重启复用已关闭 loop 的 Lock。
_request_locks: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()


async def _request_slot() -> None:
    loop = asyncio.get_running_loop()
    lock = _request_locks.setdefault(loop, asyncio.Lock())
    async with lock:
        # M02/M11 各自 20 次/2s/IP；统一每 0.12s 放行一个请求更保守。
        await asyncio.sleep(0.12)


def backfill_plan(bars: tuple[str, ...]) -> tuple[str, ...]:
    """优先补齐用户可见的大周期/分钟数据，耗时巨大的 1s 历史最后处理。"""

    priority = {NY_DAY_SOURCE_BAR: 0, "30m": 1, "15m": 2, "5m": 3, "1m": 4, "1s": 5}
    return tuple(sorted(bars, key=lambda bar: priority[bar]))


async def backfill_candles(products: list[tuple[str, str]], collector: MarketCollector) -> None:
    """独立回填每个周期，并持续校对近期缺口/未收到最终推送的 K 线。

    生命周期由 SelectionDataRuntime 管理，取消选择/停止服务时连同所有子任务取消。
    深历史（尤其 1s）不能阻塞近期修正，也不能因一个接口失败使其他周期永远不回填。
    """

    async with OkxRestClient() as client:
        async with asyncio.TaskGroup() as tasks:
            for bar in backfill_plan(TRADE_SOURCE_BARS):
                for inst_id, inst_type in products:
                    kinds = [CandleKind.TRADE]
                    if inst_type == "SWAP" and bar in MARK_SOURCE_BARS:
                        kinds.append(CandleKind.MARK)
                    for kind in kinds:
                        tasks.create_task(
                            _retry_full_history(client, collector, inst_id, kind, bar)
                        )
                        tasks.create_task(_reconcile_recent(client, collector, inst_id, kind, bar))


async def _retry_full_history(
    client: OkxRestClient, collector: MarketCollector, inst_id: str, kind: CandleKind, bar: str,
) -> None:
    while True:
        try:
            await _backfill_one(client, collector, inst_id, kind, bar)
            return
        except Exception as exc:
            logger.warning(f"candle history retry {inst_id}/{kind}/{bar}: {type(exc).__name__}")
            await asyncio.sleep(30)


async def _reconcile_recent(
    client: OkxRestClient, collector: MarketCollector, inst_id: str, kind: CandleKind, bar: str,
) -> None:
    # 1H 回看两个自然日的量，足够重建昨天/今天并覆盖 DST 的 25 小时日。
    step = {"1s": 1000, "1m": 60_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, NY_DAY_SOURCE_BAR: 3_600_000}[bar]
    overlap = 50 * 3_600_000 if bar == NY_DAY_SOURCE_BAR else max(60_000, 2 * step)
    since = int(datetime.now(UTC).timestamp() * 1000) - max(overlap, 2 * 3_600_000)
    while True:
        started_ms = int(datetime.now(UTC).timestamp() * 1000)
        try:
            await _backfill_one(client, collector, inst_id, kind, bar, since_ms=since)
            since = started_ms - overlap
        except Exception as exc:
            # 失败时不前移游标：长时间断网后仍须补齐整个断线窗口。
            logger.warning(f"candle reconcile retry {inst_id}/{kind}/{bar}: {type(exc).__name__}")
        await asyncio.sleep(30)


async def _backfill_one(
    client: OkxRestClient, collector: MarketCollector, inst_id: str, kind: CandleKind, bar: str,
    *, since_ms: int | None = None,
) -> None:
    if is_count_limited_bar(bar):
        # `1D` 已改为由 1H 源按纽约自然日派生（见 services/ny_day_candles.py），不再直接
        # 向 OKX 分页回填。这里显式拒绝而不是静默忽略：`candle_cutoff_ms("1D")` 返回
        # None，一旦真的走进下面的分页循环就会因为永远不满足停止条件而无限翻页。
        raise ValueError(f"1D 由 {NY_DAY_SOURCE_BAR} 派生，不支持直接回填: {inst_id}/{kind}")
    cutoff = candle_cutoff_ms(bar, datetime.now(UTC))
    if since_ms is not None:
        cutoff = max(cutoff or since_ms, since_ms)
    after: str | None = None
    saved = 0
    is_ny_day_source = bar == NY_DAY_SOURCE_BAR
    page_limit = 300 if kind == CandleKind.TRADE else 100
    while True:
        await _request_slot()
        rows = await (
            client.get_history_candles(
                inst_id, bar, after=after, limit=page_limit, adjust="forward"
            )
            if kind == CandleKind.TRADE
            else client.get_history_mark_price_candles(inst_id, bar, after=after, limit=page_limit)
        )
        if not rows:
            break
        for row in rows:
            # 回填按页从新到旧写入，逐根触发日线重算既慢又会反复得到不完整的当天；
            # 因此这里关闭逐根派生，整轮结束后统一重算一次。
            await collector._store_candle(
                inst_id, kind, bar, row, derive_ny_day=False, historical=True,
            )
            saved += 1
        oldest = min(int(row[0]) for row in rows)
        if after is not None and oldest >= int(after):
            raise RuntimeError("candle history cursor did not advance")
        if (cutoff is not None and oldest <= cutoff) or len(rows) < page_limit:
            break
        after = str(oldest)
    if is_ny_day_source and saved:
        # 1H 源补齐后一次性重算整个保留窗口的纽约自然日日线；逐根 1H 写入时也会重算所属
        # 那一天，但回填是从新到旧分页的，只有全部落库后最早那几天才完整。
        await rebuild_ny_day_candles(inst_id, kind)
