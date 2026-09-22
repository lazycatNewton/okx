"""M02/M11 周期与保留规则。"""

from datetime import UTC, datetime, timedelta

from okx_backend.collector.market_collector import MARK_BARS, TRADE_BARS
from okx_backend.services.candle_policy import candle_cutoff_ms, is_count_limited_bar


def test_collector_subscribes_confirmed_trade_and_mark_bars() -> None:
    assert TRADE_BARS == ("1s", "1m", "5m", "15m", "30m", "1D")
    assert MARK_BARS == ("1m", "5m", "15m", "30m", "1D")


def test_minute_candle_cutoff_is_ten_days_before_now() -> None:
    now = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    assert candle_cutoff_ms("5m", now) == int((now - timedelta(days=10)).timestamp() * 1000)


def test_one_second_candle_cutoff_remains_seven_days() -> None:
    now = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    assert candle_cutoff_ms("1s", now) == int((now - timedelta(days=7)).timestamp() * 1000)


def test_daily_candles_are_retained_by_latest_eighty_rows_not_cutoff() -> None:
    assert is_count_limited_bar("1D") is True
    assert candle_cutoff_ms("1D", datetime(2026, 9, 12, tzinfo=UTC)) is None
