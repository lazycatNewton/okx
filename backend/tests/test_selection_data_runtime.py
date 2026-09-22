from __future__ import annotations

import asyncio
from typing import Any

import pytest

from okx_backend.services.selection_data_runtime import SelectionDataRuntime


class FakeClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_new_swap_product_starts_required_backfills_and_polling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[tuple[str, str]]]] = []
    polling_clients: list[FakeClient] = []
    poll_blocker = asyncio.Event()

    async def fake_candle_backfill(products: list[tuple[str, str]], collector: Any) -> None:
        calls.append(("candles", products))

    async def fake_m25_backfill(products: list[tuple[str, str]]) -> None:
        calls.append(("m25", products))

    async def fake_start_polling(
        products: list[tuple[str, str]],
    ) -> tuple[list[asyncio.Task[Any]], FakeClient]:
        calls.append(("polling", products))
        client = FakeClient()
        polling_clients.append(client)
        return [asyncio.create_task(poll_blocker.wait())], client

    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.backfill_candles",
        fake_candle_backfill,
    )
    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.backfill_m25",
        fake_m25_backfill,
    )
    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.start_m25_polling",
        fake_start_polling,
    )

    runtime = SelectionDataRuntime()
    product = [("ETH-USDT-SWAP", "SWAP")]
    await runtime.apply_products(product, collector=object())
    await asyncio.sleep(0)

    assert calls.count(("candles", product)) == 1
    assert calls.count(("m25", product)) == 1
    assert calls.count(("polling", product)) == 1

    # 重复应用相同集合不得重复启动回填或轮询。
    await runtime.apply_products(product, collector=object())
    await asyncio.sleep(0)
    assert calls.count(("candles", product)) == 1
    assert calls.count(("m25", product)) == 1
    assert calls.count(("polling", product)) == 1

    await runtime.stop()
    assert polling_clients[0].closed is True


@pytest.mark.asyncio
async def test_removed_product_cancels_its_runtime_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backfill_blocker = asyncio.Event()
    poll_blocker = asyncio.Event()
    client = FakeClient()

    async def fake_candle_backfill(products: list[tuple[str, str]], collector: Any) -> None:
        await backfill_blocker.wait()

    async def fake_m25_backfill(products: list[tuple[str, str]]) -> None:
        await backfill_blocker.wait()

    async def fake_start_polling(
        products: list[tuple[str, str]],
    ) -> tuple[list[asyncio.Task[Any]], FakeClient]:
        return [asyncio.create_task(poll_blocker.wait())], client

    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.backfill_candles",
        fake_candle_backfill,
    )
    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.backfill_m25",
        fake_m25_backfill,
    )
    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.start_m25_polling",
        fake_start_polling,
    )

    runtime = SelectionDataRuntime()
    await runtime.apply_products([("ETH-USDT-SWAP", "SWAP")], collector=object())
    await runtime.apply_products([], collector=object())

    assert runtime.active_inst_ids == set()
    assert client.closed is True


@pytest.mark.asyncio
async def test_new_spot_product_only_starts_candle_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_candle_backfill(products: list[tuple[str, str]], collector: Any) -> None:
        calls.append("candles")

    async def forbidden_m25_backfill(products: list[tuple[str, str]]) -> None:
        raise AssertionError("SPOT must not start M25 backfill")

    async def forbidden_start_polling(products: list[tuple[str, str]]) -> Any:
        raise AssertionError("SPOT must not start M25 polling")

    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.backfill_candles",
        fake_candle_backfill,
    )
    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.backfill_m25",
        forbidden_m25_backfill,
    )
    monkeypatch.setattr(
        "okx_backend.services.selection_data_runtime.start_m25_polling",
        forbidden_start_polling,
    )

    runtime = SelectionDataRuntime()
    await runtime.apply_products([("ETH-USDT", "SPOT")], collector=object())
    await asyncio.sleep(0)

    assert calls == ["candles"]
    await runtime.stop()
