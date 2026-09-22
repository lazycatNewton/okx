"""运行期产品数据任务管理。

产品选择在应用启动后可能变化；实时 WS 订阅由 MarketCollector 管理，而 K 线/M25
历史回填与 M25 周期轮询需要在新增产品时同步建立，并在取消选择时停止。此前这些任务
只在 lifespan 启动时基于当时的产品快照创建一次，运行期间新增产品不会进入回填路径。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from loguru import logger

from okx_backend.collector.market_collector import MarketCollector
from okx_backend.services.candle_backfill import backfill_candles
from okx_backend.services.m25_stats import backfill_m25, start_m25_polling


class AsyncClosable(Protocol):
    async def aclose(self) -> None: ...


@dataclass
class _ProductRuntime:
    backfill_tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    polling_tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    polling_client: AsyncClosable | None = None


async def _run_background(label: str, operation: Callable[[], Awaitable[None]]) -> None:
    """记录单个产品回填失败，但不让后台 Task 异常无人读取。"""

    try:
        await operation()
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - 单个产品失败不得影响其他产品/实时采集
        logger.warning(f"selected-product backfill failed, skipped: {label}: {exc!r}")


class SelectionDataRuntime:
    """让已选 live 产品的回填与 M25 轮询集合持续跟随用户选择。"""

    def __init__(self) -> None:
        self._products: dict[str, _ProductRuntime] = {}
        self._lock = asyncio.Lock()

    @property
    def active_inst_ids(self) -> set[str]:
        return set(self._products)

    async def apply_products(
        self,
        products: list[tuple[str, str]],
        collector: MarketCollector,
    ) -> None:
        """为新增产品立即启动回填/轮询，为移除产品停止对应任务。

        `products` 是全部当前已选且 live 的 `(instId, instType)`；重复调用相同集合幂等。
        """

        desired = dict(products)
        async with self._lock:
            removed = set(self._products) - set(desired)
            for inst_id in removed:
                runtime = self._products.pop(inst_id)
                await self._stop_product(runtime)

            for inst_id, inst_type in desired.items():
                if inst_id in self._products:
                    continue
                self._products[inst_id] = await self._start_product(
                    inst_id,
                    inst_type,
                    collector,
                )

    async def _start_product(
        self,
        inst_id: str,
        inst_type: str,
        collector: MarketCollector,
    ) -> _ProductRuntime:
        product = [(inst_id, inst_type)]
        runtime = _ProductRuntime()

        runtime.backfill_tasks.append(
            asyncio.create_task(
                _run_background(
                    f"candles {inst_id}",
                    lambda: backfill_candles(product, collector),
                )
            )
        )

        if inst_type == "SWAP":
            runtime.backfill_tasks.append(
                asyncio.create_task(
                    _run_background(
                        f"M25 {inst_id}",
                        lambda: backfill_m25(product),
                    )
                )
            )
            polling_tasks, polling_client = await start_m25_polling(product)
            runtime.polling_tasks.extend(polling_tasks)
            runtime.polling_client = polling_client

        logger.info(f"selected-product data tasks started: {inst_id} ({inst_type})")
        return runtime

    async def _stop_product(self, runtime: _ProductRuntime) -> None:
        tasks = [*runtime.backfill_tasks, *runtime.polling_tasks]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if runtime.polling_client is not None:
            await runtime.polling_client.aclose()

    async def stop(self) -> None:
        async with self._lock:
            runtimes = list(self._products.values())
            self._products.clear()
            for runtime in runtimes:
                await self._stop_product(runtime)


_selection_data_runtime: SelectionDataRuntime | None = None


def get_selection_data_runtime() -> SelectionDataRuntime:
    global _selection_data_runtime
    if _selection_data_runtime is None:
        _selection_data_runtime = SelectionDataRuntime()
    return _selection_data_runtime
