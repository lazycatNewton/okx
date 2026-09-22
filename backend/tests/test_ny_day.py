"""纽约自然日分桶与重采样的回归测试。

核心风险是夏令时：纽约 00:00 在 EDT 下是 UTC 04:00、在 EST 下是 UTC 05:00，
固定偏移（哪怕是用户口中的 UTC-4）会在冬令时整整错一小时；切换当天的自然日还分别
只有 23 小时和 25 小时。下面的用例都用真实的切换日做断言。
"""

from datetime import UTC, datetime

from okx_backend.services.m25_stats import (
    ny_day_open,
    ny_day_taker_volume_sum,
    resample_ny_day,
    source_period,
)
from okx_backend.services.ny_day import (
    decimal_sum,
    group_by_ny_day,
    next_ny_day_start_ms,
    ny_day_start_days_ago,
    ny_day_start_ms,
)
from okx_backend.services.ny_day_candles import aggregate_ny_day


def _ms(text: str) -> int:
    return int(datetime.fromisoformat(text).timestamp() * 1000)


def test_day_start_uses_edt_offset_in_summer() -> None:
    # 2026-09-16 的纽约 00:00 = UTC 04:00（EDT, UTC-4）。
    assert ny_day_start_ms(_ms("2026-09-16T12:34:56+00:00")) == _ms("2026-09-16T04:00:00+00:00")


def test_day_start_uses_est_offset_in_winter() -> None:
    # 2026-01-15 的纽约 00:00 = UTC 05:00（EST, UTC-5）；写死 UTC-4 在这里就会错一小时。
    assert ny_day_start_ms(_ms("2026-01-15T12:34:56+00:00")) == _ms("2026-01-15T05:00:00+00:00")


def test_okx_utc8_daily_bucket_is_not_a_new_york_day_start() -> None:
    """OKX `1D` 的 ts 落在 UTC 16:00（UTC+8 的 0 点），即纽约的中午，这正是要修正的偏差。"""

    okx_daily_ts = _ms("2026-09-15T16:00:00+00:00")
    assert ny_day_start_ms(okx_daily_ts) == _ms("2026-09-15T04:00:00+00:00")
    assert okx_daily_ts != ny_day_start_ms(okx_daily_ts)


def test_spring_forward_day_has_23_hours() -> None:
    day = ny_day_start_ms(_ms("2026-03-08T12:00:00+00:00"))
    assert (next_ny_day_start_ms(day) - day) == 23 * 3_600_000


def test_fall_back_day_has_25_hours() -> None:
    day = ny_day_start_ms(_ms("2026-11-01T12:00:00+00:00"))
    assert (next_ny_day_start_ms(day) - day) == 25 * 3_600_000


def test_days_ago_walks_wall_clock_across_a_dst_switch() -> None:
    """跨夏令时往前数 N 天必须仍然落在当地 00:00，而不是被固定秒数拖偏一小时。"""

    start = ny_day_start_days_ago(10, datetime.fromisoformat("2026-11-05T12:00:00+00:00"))
    assert start == _ms("2026-10-26T04:00:00+00:00")  # 10 月 26 日仍是 EDT


def test_group_by_ny_day_splits_at_new_york_midnight() -> None:
    rows = [
        (_ms("2026-09-16T03:00:00+00:00"), {"v": "before"}),  # 纽约 15 日 23:00
        (_ms("2026-09-16T04:00:00+00:00"), {"v": "open"}),    # 纽约 16 日 00:00
        (_ms("2026-09-16T05:00:00+00:00"), {"v": "after"}),
    ]
    grouped = group_by_ny_day(rows)
    assert sorted(grouped) == [
        _ms("2026-09-15T04:00:00+00:00"),
        _ms("2026-09-16T04:00:00+00:00"),
    ]
    assert [p["v"] for _, p in grouped[_ms("2026-09-16T04:00:00+00:00")]] == ["open", "after"]


def test_decimal_sum_keeps_fixed_point_and_returns_none_without_values() -> None:
    assert decimal_sum(["0.00000001", "0.00000002"]) == "0.00000003"
    assert decimal_sum([None, ""]) is None


# -- K 线日聚合 --------------------------------------------------------------
def _hour(ts: int, o: str, h: str, low: str, c: str, vol: str) -> dict:
    return {"ts": str(ts), "o": o, "h": h, "l": low, "c": c,
            "vol": vol, "volCcy": vol, "volCcyQuote": vol, "confirm": "1"}


def test_daily_candle_takes_first_open_last_close_and_summed_volume() -> None:
    day = _ms("2026-09-16T04:00:00+00:00")
    rows = [
        _hour(day, "10", "12", "9", "11", "100"),
        _hour(day + 3_600_000, "11", "15", "10", "14", "50"),
    ]
    candle = aggregate_ny_day(day, rows, now_ms=day + 2 * 3_600_000)
    assert candle is not None
    assert candle["ts"] == str(day)
    assert (candle["o"], candle["h"], candle["l"], candle["c"]) == ("10", "15", "9", "14")
    assert candle["vol"] == "150"
    assert candle["confirm"] == "0"


def test_daily_candle_is_unconfirmed_while_the_new_york_day_is_still_running() -> None:
    day = _ms("2026-09-16T04:00:00+00:00")
    rows = [_hour(day, "10", "12", "9", "11", "100")]
    candle = aggregate_ny_day(day, rows, now_ms=_ms("2026-09-16T10:00:00+00:00"))
    assert candle is not None
    assert candle["confirm"] == "0"


def test_daily_candle_must_not_invent_the_midnight_open_from_a_later_hour() -> None:
    day = _ms("2026-09-16T04:00:00+00:00")
    rows = [_hour(day + 3_600_000, "10", "12", "9", "11", "100")]
    assert aggregate_ny_day(day, rows, now_ms=day + 4 * 3_600_000) is None


def test_partial_ended_day_must_not_freeze_incomplete_high_low_and_close() -> None:
    day = _ms("2026-09-16T04:00:00+00:00")
    rows = [_hour(day, "10", "12", "9", "11", "100")]
    assert aggregate_ny_day(day, rows, now_ms=day + 25 * 3_600_000) is None


def test_daily_confirmation_requires_every_source_hour_including_dst_days() -> None:
    for date in ["2026-03-08T05:00:00+00:00", "2026-09-16T04:00:00+00:00",
                 "2026-11-01T04:00:00+00:00"]:
        day = _ms(date)
        end = next_ny_day_start_ms(day)
        rows = [_hour(ts, "10", "12", "9", "11", "1")
                for ts in range(day, end, 3_600_000)]
        candle = aggregate_ny_day(day, rows, now_ms=end)
        assert candle is not None and candle["confirm"] == "1"
        assert candle["vol"] == str(len(rows))
        rows[-1]["confirm"] = "0"
        candle = aggregate_ny_day(day, rows, now_ms=end)
        assert candle is not None and candle["confirm"] == "0"
        assert aggregate_ny_day(day, rows[:2] + rows[3:], now_ms=end) is None


# -- M25 日重采样 ------------------------------------------------------------
def test_source_period_maps_daily_to_the_official_hourly_granularity() -> None:
    assert source_period("1D") == "1H"
    assert source_period("5m") == "5m"
    assert source_period("1H") == "1H"


def test_snapshot_metric_takes_the_reading_at_new_york_midnight() -> None:
    day = _ms("2026-09-16T04:00:00+00:00")
    hourly = [
        (day, {"ts": str(day), "oi": "100"}),
        (day + 3_600_000, {"ts": str(day + 3_600_000), "oi": "200"}),
    ]
    (out_day, payload), = resample_ny_day(hourly, ny_day_open)
    assert out_day == day
    assert payload["oi"] == "100"
    assert (payload["srcPeriod"], payload["srcTs"]) == ("1H", str(day))


def test_taker_volume_metric_sums_across_the_new_york_day() -> None:
    day = _ms("2026-09-16T04:00:00+00:00")
    hourly = [
        (day, {"ts": str(day), "sellVol": "1.5", "buyVol": "2"}),
        (day + 3_600_000, {"ts": str(day + 3_600_000), "sellVol": "0.5", "buyVol": "3"}),
    ]
    (_, payload), = resample_ny_day(hourly, ny_day_taker_volume_sum)
    assert (payload["sellVol"], payload["buyVol"]) == ("2.0", "5")
    assert payload["srcHours"] == "2"


def test_partial_oldest_day_is_skipped_instead_of_written_incomplete() -> None:
    """分页窗口最老的一天通常只有半天数据，写进去会得到错误的日界值/日累计量。"""

    day = _ms("2026-09-16T04:00:00+00:00")
    hourly = [(day + 10 * 3_600_000, {"ts": str(day + 10 * 3_600_000), "oi": "100"})]
    assert resample_ny_day(hourly, ny_day_open) == []
    assert resample_ny_day(hourly, ny_day_taker_volume_sum) == []


def test_resample_covers_each_new_york_day_once() -> None:
    hourly = [
        (_ms("2026-09-16T04:00:00+00:00"), {"ts": "a", "oi": "1"}),
        (_ms("2026-09-16T20:00:00+00:00"), {"ts": "b", "oi": "2"}),
        (_ms("2026-09-17T04:00:00+00:00"), {"ts": "c", "oi": "3"}),
    ]
    days = [day for day, _ in resample_ny_day(hourly, ny_day_open)]
    assert days == [
        _ms("2026-09-16T04:00:00+00:00"),
        _ms("2026-09-17T04:00:00+00:00"),
    ]


def test_utc_helpers_do_not_depend_on_the_machine_timezone() -> None:
    """全部换算都以 UTC 输入/输出，不读本机时区；这里固定一个 UTC 时刻断言。"""

    assert ny_day_start_ms(int(datetime(2026, 9, 16, 4, tzinfo=UTC).timestamp() * 1000)) == _ms(
        "2026-09-16T04:00:00+00:00"
    )
