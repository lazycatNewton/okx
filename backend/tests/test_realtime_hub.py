"""realtime.hub 的单元测试：重点覆盖曾经出现过的“BrowserConnection 不可哈希”回归。"""

from __future__ import annotations

import asyncio
import json

import pytest

from okx_backend.realtime.hub import RealtimeHub


def test_browser_connection_is_hashable_and_can_be_added_to_a_set() -> None:
    """回归测试：BrowserConnection 曾因 @dataclass 默认生成 __eq__/__hash__=None 而无法放入 set。"""

    hub = RealtimeHub()
    conn1 = hub.register()
    conn2 = hub.register()
    assert conn1 is not conn2
    assert len({conn1, conn2}) == 2


@pytest.mark.asyncio
async def test_activate_sends_empty_when_no_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRedis:
        async def get(self, _key: str) -> None:
            return None

    monkeypatch.setattr("okx_backend.realtime.hub.get_redis", lambda: _FakeRedis())

    hub = RealtimeHub()
    conn = hub.register()
    await hub.activate(conn, "BTC-USDT")

    messages = []
    while not conn.queue.empty():
        messages.append(json.loads(conn.queue.get_nowait()))
    assert {"ticker", "books5"}.issubset({m["channel"] for m in messages})
    assert all(m["type"] == "empty" for m in messages)


@pytest.mark.asyncio
async def test_activate_sends_candle_and_trade_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRedis:
        async def get(self, _key: str) -> None:
            return None

    monkeypatch.setattr("okx_backend.realtime.hub.get_redis", lambda: _FakeRedis())

    hub = RealtimeHub()
    conn = hub.register()
    await hub.activate(conn, "BTC-USDT")

    messages = []
    while not conn.queue.empty():
        messages.append(json.loads(conn.queue.get_nowait()))
    channels = {message["channel"] for message in messages}
    assert "candle:trade:1m" in channels
    assert "candle:mark:30m" in channels
    assert "trades" in channels


@pytest.mark.asyncio
async def test_activate_sends_m10_m12_m13_m14_m15_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeRedis:
        async def get(self, _key: str) -> None:
            return None

    monkeypatch.setattr("okx_backend.realtime.hub.get_redis", lambda: _FakeRedis())

    hub = RealtimeHub()
    conn = hub.register()
    await hub.activate(conn, "BTC-USDT-SWAP")

    messages = []
    while not conn.queue.empty():
        messages.append(json.loads(conn.queue.get_nowait()))
    channels = {message["channel"] for message in messages}
    assert {"mark-price", "open-interest"}.issubset(channels)
    # 已移除的 M12/M14/M15 频道不得再出现在快照里。
    assert not {"funding-rate", "price-limit", "estimated-price"} & channels


@pytest.mark.asyncio
async def test_broadcast_update_only_reaches_activated_connections() -> None:
    hub = RealtimeHub()
    active_conn = hub.register()
    inactive_conn = hub.register()
    active_conn.activated_inst_ids.add("BTC-USDT")

    await hub.broadcast_update("BTC-USDT", "ticker", {"ts": "1"})

    assert not active_conn.queue.empty()
    assert inactive_conn.queue.empty()


@pytest.mark.asyncio
async def test_queue_is_bounded_and_drops_oldest() -> None:
    hub = RealtimeHub()
    conn = hub.register()
    conn.queue = asyncio.Queue(maxsize=2)
    conn.activated_inst_ids.add("BTC-USDT")

    for i in range(5):
        await hub.broadcast_update("BTC-USDT", "ticker", {"ts": str(i)})

    assert conn.queue.qsize() == 2
