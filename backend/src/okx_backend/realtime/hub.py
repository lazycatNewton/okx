"""浏览器实时分发中枢（单实例进程内广播）。

依据 okx-requirements.md「浏览器仅调用本产品后端」：
- 浏览器通过 `activate-product`/`deactivate-product` 声明当前需要哪些产品的实时分发；
  这只影响本连接收到的消息，不改变后台持续采集集合（那部分由 MarketCollector 独立维护）。
- 激活后先发送各已知频道的 `snapshot`（来自 Redis 最新缓存），再持续推送 `update`。
- 重连后同样遵循“先 snapshot 再 update”。

多实例部署下进程内广播不够用（需要 Redis Pub/Sub 或等价机制），但部署拓扑与单/多实例仍是
用户明确暂缓的事项（见 AGENTS.md），此处诚实标注为当前单实例假设，不在此处过度设计。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from okx_backend.cache import get_redis

TRADE_BARS = ("1s", "1m", "5m", "15m", "30m", "1D")

CHANNEL_KEYS = {
    "ticker": "m01:latest:{inst_id}",
    "books5": "m05:latest:{inst_id}",
    "trades": "m03:latest:{inst_id}",
    "mark-price": "m10:latest:{inst_id}",
    "open-interest": "m13:latest:{inst_id}",
    **{
        f"candle:trade:{bar}": f"m02:latest:{{inst_id}}:{bar}"
        for bar in TRADE_BARS
    },
}


@dataclass(eq=False)
class BrowserConnection:
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=1000))
    activated_inst_ids: set[str] = field(default_factory=set)

    async def send_envelope(
        self, type_: str, inst_id: str, channel: str, data: object
    ) -> None:
        envelope = {
            "type": type_,
            "instId": inst_id,
            "channel": channel,
            "data": data,
            "sourceTs": data.get("ts") if isinstance(data, dict) else None,
            "receivedAt": datetime.now(UTC).isoformat(),
        }
        if self.queue.full():
            # 有界队列：丢弃最旧的一条，保证慢消费者不会无限堆积内存。
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
        await self.queue.put(json.dumps(envelope))


class RealtimeHub:
    def __init__(self) -> None:
        self._connections: set[BrowserConnection] = set()

    def register(self) -> BrowserConnection:
        conn = BrowserConnection()
        self._connections.add(conn)
        return conn

    def unregister(self, conn: BrowserConnection) -> None:
        self._connections.discard(conn)

    async def activate(self, conn: BrowserConnection, inst_id: str) -> None:
        conn.activated_inst_ids.add(inst_id)
        await self._send_snapshot(conn, inst_id)

    def deactivate(self, conn: BrowserConnection, inst_id: str) -> None:
        conn.activated_inst_ids.discard(inst_id)

    async def _send_snapshot(self, conn: BrowserConnection, inst_id: str) -> None:
        redis = get_redis()
        for channel, key_tpl in CHANNEL_KEYS.items():
            raw = await redis.get(key_tpl.format(inst_id=inst_id))
            if raw is None:
                await conn.send_envelope("empty", inst_id, channel, None)
            else:
                await conn.send_envelope("snapshot", inst_id, channel, json.loads(raw))

    async def broadcast_update(self, inst_id: str, channel: str, data: object) -> None:
        for conn in list(self._connections):
            if inst_id in conn.activated_inst_ids:
                await conn.send_envelope("update", inst_id, channel, data)


_hub: RealtimeHub | None = None


def get_hub() -> RealtimeHub:
    global _hub
    if _hub is None:
        _hub = RealtimeHub()
    return _hub
