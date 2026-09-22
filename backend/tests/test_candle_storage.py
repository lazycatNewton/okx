"""真实采集调用边界的历史/实时隔离回归，不连接数据库或 OKX。"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import mysql

from okx_backend.collector import market_collector as module
from okx_backend.db.models import CandleKind


@pytest.fixture
def storage(monkeypatch):
    session = AsyncMock()

    @asynccontextmanager
    async def scope():
        yield session

    cache = AsyncMock(return_value=True)
    hub = AsyncMock()
    monkeypatch.setattr(module, "session_scope", scope)
    monkeypatch.setattr(module, "cache_latest_candle", cache)
    monkeypatch.setattr(module, "get_hub", lambda: hub)
    return module.MarketCollector(), session, cache, hub


def row(confirm):
    return ["1790076600000", "100", "102", "99", "101", "1", "1", "1", confirm]


@pytest.mark.asyncio
async def test_history_cannot_publish_an_old_bar_as_latest(storage):
    collector, session, cache, hub = storage
    await collector._store_candle("TEST-USDT", CandleKind.TRADE, "5m", row("1"), historical=True)
    session.execute.assert_awaited_once()
    cache.assert_not_awaited()
    hub.broadcast_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_unfinished_rest_snapshot_cannot_shrink_live_high_low_or_close(storage):
    collector, session, cache, hub = storage
    await collector._store_candle("TEST-USDT", CandleKind.TRADE, "5m", row("0"), historical=True)
    session.execute.assert_not_awaited()
    cache.assert_not_awaited()
    hub.broadcast_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_unconfirmed_ws_update_guards_every_sql_field_with_confirm_last(storage):
    collector, session, cache, hub = storage
    await collector._store_candle("TEST-USDT", CandleKind.TRADE, "5m", row("0"))
    stmt = session.execute.await_args.args[0]
    sql = str(stmt.compile(dialect=mysql.dialect()))
    updates = sql.split("ON DUPLICATE KEY UPDATE ")[1]
    for field in ["o", "h", "l", "c", "vol", "vol_ccy", "vol_ccy_quote", "received_at", "confirm"]:
        assert f"{field} = CASE WHEN (candles.confirm !=" in updates
    assert updates.rindex("confirm = CASE") > updates.rindex("received_at = CASE")
    cache.assert_awaited_once()
    hub.broadcast_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejected_old_cache_version_is_not_broadcast_as_live(storage):
    collector, session, cache, hub = storage
    cache.return_value = False
    await collector._store_candle("TEST-USDT", CandleKind.TRADE, "5m", row("0"))
    session.execute.assert_awaited_once()
    hub.broadcast_update.assert_not_awaited()
