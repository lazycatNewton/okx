"""保留清理 SQL 构造的单元测试（编译级，不需要真实数据库连接）。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.dialects import mysql

from okx_backend.db.models import Candle, TickerSnapshot
from okx_backend.services.retention import (
    DAILY_CANDLE_KEEP,
    build_candle_age_delete,
    build_daily_candle_cap_subquery,
    build_simple_cutoff_delete,
    run_retention_cleanup_forever,
)


def test_simple_cutoff_delete_uses_seven_day_boundary_by_default() -> None:
    now = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)
    stmt = build_simple_cutoff_delete(TickerSnapshot, TickerSnapshot.ts_ms, 7, now)
    expected_cutoff = int((now - timedelta(days=7)).timestamp() * 1000)
    compiled = str(stmt.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "DELETE FROM m01_ticker_snapshots" in compiled
    assert str(expected_cutoff) in compiled


def test_candle_age_delete_skips_daily_bar() -> None:
    """1D 由「按条数保留最新 80 根」清理，不适用按时长删除，否则会双重清理冲突。"""

    assert build_candle_age_delete("1D", datetime.now(UTC)) is None


def test_candle_age_delete_uses_ten_day_boundary_for_minute_bars() -> None:
    now = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)
    stmt = build_candle_age_delete("5m", now)
    assert stmt is not None
    expected_cutoff = int((now - timedelta(days=10)).timestamp() * 1000)
    compiled = str(stmt.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "DELETE FROM candles" in compiled
    assert str(expected_cutoff) in compiled


def test_candle_age_delete_uses_seven_day_boundary_for_1s() -> None:
    now = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)
    stmt = build_candle_age_delete("1s", now)
    assert stmt is not None
    expected_cutoff = int((now - timedelta(days=7)).timestamp() * 1000)
    compiled = str(stmt.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert str(expected_cutoff) in compiled


def test_daily_candle_cap_subquery_partitions_by_inst_and_kind() -> None:
    """按 inst_id+kind 分组各自保留最新 80 根，而不是全表只留 80 根。"""

    subquery = build_daily_candle_cap_subquery()
    compiled = str(subquery.compile(dialect=mysql.dialect()))
    assert "PARTITION BY" in compiled.upper()
    assert "inst_id" in compiled
    assert "kind" in compiled
    assert str(DAILY_CANDLE_KEEP) in compiled or "rn >" in compiled.lower()


def test_daily_candle_cap_subquery_only_targets_1d_bar() -> None:
    subquery = build_daily_candle_cap_subquery()
    compiled = str(
        subquery.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "bar" in compiled
    assert "1D" in compiled


def test_candle_model_has_kind_and_bar_columns_for_partitioning() -> None:
    # 防止未来重构误删 Candle.kind/bar，导致 retention.py 的分组清理静默失效。
    assert hasattr(Candle, "kind")
    assert hasattr(Candle, "bar")


@pytest.mark.asyncio
async def test_run_retention_cleanup_forever_survives_a_failed_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单轮清理抛异常时，后台任务必须记录并继续下一轮，而不是让整个循环退出——
    否则一次数据库瞬时故障会永久停掉后续所有清理。"""

    call_count = 0

    async def _flaky_cleanup(now: datetime | None = None) -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated transient db error")
        return {}

    monkeypatch.setattr(
        "okx_backend.services.retention.run_retention_cleanup", _flaky_cleanup
    )

    task = asyncio.create_task(run_retention_cleanup_forever(interval_seconds=0))
    for _ in range(100):
        if call_count >= 2:
            break
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert call_count >= 2
