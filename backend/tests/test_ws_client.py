"""OkxWsClient 的订阅集合与 ChannelArg 去重逻辑单元测试（不建立真实连接）。"""

from __future__ import annotations

from okx_backend.okx_client.ws_client import ChannelArg, OkxWsClient


def test_channel_arg_is_hashable_and_deduplicates() -> None:
    a = ChannelArg(channel="tickers", inst_id="BTC-USDT")
    b = ChannelArg(channel="tickers", inst_id="BTC-USDT")
    c = ChannelArg(channel="tickers", inst_id="ETH-USDT")
    assert a == b
    assert len({a, b, c}) == 2


def test_channel_arg_to_ws_arg_only_includes_set_fields() -> None:
    arg = ChannelArg(channel="mark-price", inst_id="BTC-USDT-SWAP")
    ws_arg = arg.to_ws_arg()
    assert ws_arg == {"channel": "mark-price", "instId": "BTC-USDT-SWAP"}
    assert "instType" not in ws_arg


async def _noop_handler(_message: dict) -> None:
    return None


def test_set_desired_channels_replaces_previous_set() -> None:
    client = OkxWsClient("wss://example.invalid/ws", _noop_handler)
    first = {ChannelArg(channel="tickers", inst_id="BTC-USDT")}
    second = {ChannelArg(channel="tickers", inst_id="ETH-USDT")}

    client.set_desired_channels(first)
    assert client._desired == first  # noqa: SLF001 - 白盒测试内部状态

    client.set_desired_channels(second)
    assert client._desired == second  # noqa: SLF001
