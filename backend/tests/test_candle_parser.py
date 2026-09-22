"""M11 标记价格 K 线行的字段解析回归测试。"""

from okx_backend.collector.market_collector import parse_candle_row
from okx_backend.db.models import CandleKind


def test_mark_price_candle_six_columns_maps_sixth_value_to_confirm() -> None:
    parsed = parse_candle_row(CandleKind.MARK, ["1", "10", "12", "9", "11", "0"])
    assert parsed.confirm == "0"
    assert parsed.vol is None


def test_trade_candle_nine_columns_preserves_volume_and_confirm() -> None:
    parsed = parse_candle_row(CandleKind.TRADE, ["1", "10", "12", "9", "11", "3", "4", "5", "1"])
    assert parsed.vol == "3"
    assert parsed.confirm == "1"
