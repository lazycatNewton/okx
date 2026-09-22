"""M02 成交价 K 线行的字段解析回归测试。"""

from okx_backend.collector.market_collector import parse_candle_row


def test_trade_candle_nine_columns_preserves_volume_and_confirm() -> None:
    parsed = parse_candle_row(["1", "10", "12", "9", "11", "3", "4", "5", "1"])
    assert parsed.vol == "3"
    assert parsed.confirm == "1"
