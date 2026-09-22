"""历史 K 线回填的复权参数使用回归测试。"""

from __future__ import annotations

from typing import Any

import pytest

from okx_backend.db.models import CandleKind
from okx_backend.services.candle_backfill import _backfill_one


class _RecordingRestClient:
    def __init__(self) -> None:
        self.history_candle_calls: list[dict[str, Any]] = []
        self.mark_price_calls: list[dict[str, Any]] = []

    async def get_history_candles(self, inst_id: str, bar: str, **kwargs: Any) -> list[list[str]]:
        self.history_candle_calls.append({"inst_id": inst_id, "bar": bar, **kwargs})
        return []

    async def get_history_mark_price_candles(
        self, inst_id: str, bar: str, **kwargs: Any
    ) -> list[list[str]]:
        self.mark_price_calls.append({"inst_id": inst_id, "bar": bar, **kwargs})
        return []


class _NoopCollector:
    async def _store_candle(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_trade_price_backfill_requests_forward_adjusted_history() -> None:
    client = _RecordingRestClient()
    await _backfill_one(client, _NoopCollector(), "SPCX-USDT-SWAP", CandleKind.TRADE, "1H")  # type: ignore[arg-type]
    assert client.history_candle_calls[0]["adjust"] == "forward"


@pytest.mark.asyncio
async def test_mark_price_backfill_does_not_pass_unsupported_adjust_param() -> None:
    client = _RecordingRestClient()
    await _backfill_one(client, _NoopCollector(), "SPCX-USDT-SWAP", CandleKind.MARK, "1H")  # type: ignore[arg-type]
    assert "adjust" not in client.mark_price_calls[0]
