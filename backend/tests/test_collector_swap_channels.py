"""M10/M13 采集器的订阅集合与字段映射单元测试（不需要真实 WS/DB 连接）。"""

from __future__ import annotations

from okx_backend.collector.market_collector import MarketCollector, _to_optional_int
from okx_backend.okx_client.ws_client import ChannelArg


def test_swap_product_subscribes_m10_m13_public_channels() -> None:
    collector = MarketCollector()
    collector.apply_selected_products([("BTC-USDT-SWAP", "SWAP", "BTC-USDT")])
    desired = collector._public_ws._desired  # noqa: SLF001 - 白盒测试内部状态

    assert ChannelArg(channel="mark-price", inst_id="BTC-USDT-SWAP") in desired
    assert ChannelArg(channel="open-interest", inst_id="BTC-USDT-SWAP") in desired
    # 已移除的 M12/M14/M15 频道不得再出现在订阅集合里。
    for channel in ("funding-rate", "price-limit", "estimated-price"):
        assert all(arg.channel != channel for arg in desired)


def test_spot_product_does_not_subscribe_swap_only_channels() -> None:
    """需求文档：M10/M13 仅适用于永续，不应扩大到现货。"""

    collector = MarketCollector()
    collector.apply_selected_products([("BTC-USDT", "SPOT", None)])
    desired = collector._public_ws._desired  # noqa: SLF001

    assert ChannelArg(channel="mark-price", inst_id="BTC-USDT") not in desired
    assert ChannelArg(channel="open-interest", inst_id="BTC-USDT") not in desired
    # tickers/books5/trades 仍应正常订阅——不是本测试关注点，但确认过滤没有误伤基础频道。
    assert ChannelArg(channel="tickers", inst_id="BTC-USDT") in desired


def test_to_optional_int_handles_empty_and_none() -> None:
    assert _to_optional_int(None) is None
    assert _to_optional_int("") is None
    assert _to_optional_int("1622851200000") == 1622851200000
