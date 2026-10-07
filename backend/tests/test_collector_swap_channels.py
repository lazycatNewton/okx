"""采集器订阅集合单元测试（不需要真实 WS/DB 连接）。"""

from __future__ import annotations

from okx_backend.collector.market_collector import MarketCollector, _to_optional_int
from okx_backend.okx_client.ws_client import ChannelArg

# 已按用户指令移除的公共频道：M10/M13（2026-10-07）与更早的 M12/M14/M15。
REMOVED_PUBLIC_CHANNELS = (
    "mark-price", "open-interest", "funding-rate", "price-limit", "estimated-price",
)


def test_swap_product_does_not_subscribe_removed_channels() -> None:
    collector = MarketCollector()
    collector.apply_selected_products([("BTC-USDT-SWAP", "SWAP", "BTC-USDT")])
    desired = collector._public_ws._desired  # noqa: SLF001 - 白盒测试内部状态

    assert {arg.channel for arg in desired} == {"tickers", "books5", "trades"}
    for channel in REMOVED_PUBLIC_CHANNELS:
        assert all(arg.channel != channel for arg in desired)


def test_spot_product_subscribes_same_public_channels() -> None:
    collector = MarketCollector()
    collector.apply_selected_products([("BTC-USDT", "SPOT", None)])
    desired = collector._public_ws._desired  # noqa: SLF001

    assert desired == {
        ChannelArg(channel=channel, inst_id="BTC-USDT")
        for channel in ("tickers", "books5", "trades")
    }


def test_to_optional_int_handles_empty_and_none() -> None:
    assert _to_optional_int(None) is None
    assert _to_optional_int("") is None
    assert _to_optional_int("1622851200000") == 1622851200000
