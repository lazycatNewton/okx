"""OKX 公共 WebSocket 客户端（public / business）。

按 HANDOFF.md 第 7 节"未确认方案备忘"中的连接生命周期设计作为本次实现基线
（已向用户确认可作为默认落地）：
- 应用层心跳：可配置的空闲发送 `ping`，超时未收到 `pong` 则判定连接失活并重连。
- 指数退避重连（1,2,4,8,...最大 30s，含抖动）。
- 连接代次（generation）：每次重连生成新代次，旧代次的回调/超时判定一律忽略，防止旧连接的
  延迟消息覆盖新连接状态。
- desired / active 订阅集合：`desired` 由上层（采集调度器）维护，连接建立/重连后按最新
  desired 重新发送 subscribe，而不是替 desired 做增量运算。

限制说明（诚实标注，非需求确认）：本模块本身不知道每个频道的“已选集合”业务规则（如仅 live
产品、SWAP-only 频道等）；这些过滤逻辑属于上层调用方（collector）职责，本模块只保证连接、
订阅去重、心跳和重连按上述基线工作。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import websockets
from loguru import logger
from websockets.asyncio.client import ClientConnection

MessageHandler = Callable[[dict], Awaitable[None]]


@dataclass(frozen=True)
class ChannelArg:
    """订阅参数的规范化键；比较/去重以此为准（OKX `args` 元素的字段组合）。"""

    channel: str
    inst_id: str | None = None
    inst_type: str | None = None
    inst_family: str | None = None

    def to_ws_arg(self) -> dict:
        arg: dict[str, str] = {"channel": self.channel}
        if self.inst_id is not None:
            arg["instId"] = self.inst_id
        if self.inst_type is not None:
            arg["instType"] = self.inst_type
        if self.inst_family is not None:
            arg["instFamily"] = self.inst_family
        return arg


@dataclass
class _ReconnectPolicy:
    base_seconds: float = 1.0
    max_seconds: float = 30.0
    factor: float = 2.0

    def delay(self, attempt: int) -> float:
        raw = min(self.base_seconds * (self.factor**attempt), self.max_seconds)
        jitter = raw * random.uniform(0.0, 0.3)
        return raw + jitter


class OkxWsClient:
    """单条 OKX WS 连接的管理器（public 或 business 一个 URL 对应一个实例）。

    调用方通过 `desired_channels` 声明当前需要订阅的频道集合（线程/协程安全地整体替换），
    本类负责保持连接、按最新 desired 重新订阅、心跳与重连。
    """

    def __init__(
        self,
        url: str,
        on_message: MessageHandler,
        ping_idle_seconds: float = 20.0,
        pong_timeout_seconds: float = 10.0,
        reconnect_policy: _ReconnectPolicy | None = None,
        login_args_provider: Callable[[], list[dict]] | None = None,
    ) -> None:
        self._url = url
        self._on_message = on_message
        self._ping_idle_seconds = ping_idle_seconds
        self._pong_timeout_seconds = pong_timeout_seconds
        self._reconnect_policy = reconnect_policy or _ReconnectPolicy()
        # 私有频道（如 M23 economic-calendar）需要先 `op=login` 再订阅；本类不知道
        # 具体签名细节，只在每次（重）连接时调用调用方提供的 `login_args_provider()`
        # 取得最新签名的 login args（时间戳必须实时生成，不能复用旧连接的签名）。
        self._login_args_provider = login_args_provider
        self._login_event = asyncio.Event()
        self._login_failed = False

        self._desired: set[ChannelArg] = set()
        self._active: set[ChannelArg] = set()
        self._generation = 0
        self._stop = False
        self._run_task: asyncio.Task | None = None
        self._conn: ClientConnection | None = None
        self._last_message_at = 0.0

    # -- 外部接口 --------------------------------------------------------
    def set_desired_channels(self, channels: set[ChannelArg]) -> None:
        """整体替换 desired 集合；实际增量订阅/退订在下一次事件循环中处理。"""

        self._desired = set(channels)

    def start(self) -> None:
        if self._run_task is None:
            self._stop = False
            self._run_task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stop = True
        if self._run_task is not None:
            self._run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._run_task
            self._run_task = None
        if self._conn is not None:
            with contextlib.suppress(Exception):
                await self._conn.close()

    @property
    def active_channels(self) -> frozenset[ChannelArg]:
        return frozenset(self._active)

    # -- 内部实现 --------------------------------------------------------
    async def _run_forever(self) -> None:
        attempt = 0
        while not self._stop:
            self._generation += 1
            generation = self._generation
            try:
                async with websockets.connect(self._url, open_timeout=10) as conn:
                    self._conn = conn
                    self._active = set()
                    attempt = 0
                    logger.info(f"ws connected generation={generation} url={self._url}")
                    if self._login_args_provider is not None:
                        self._login_event.clear()
                        self._login_failed = False
                        await conn.send(
                            json.dumps({"op": "login", "args": self._login_args_provider()})
                        )
                        # 登录响应由 _reader_loop 消费；在此等待，避免登录完成前发送
                        # subscribe（未登录状态下私有频道的 subscribe 会被 OKX 拒绝）。
                        # 心跳/resync 循环与 reader 循环并发跑，所以这里手动读取直到
                        # 登录事件被 reader 标记，而不是阻塞整个连接建立流程。
                        login_reader = asyncio.create_task(
                            self._reader_loop(conn, generation)
                        )
                        try:
                            await asyncio.wait_for(self._login_event.wait(), timeout=10.0)
                        except TimeoutError:
                            login_reader.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await login_reader
                            raise RuntimeError("ws login timed out") from None
                        if self._login_failed:
                            login_reader.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await login_reader
                            raise RuntimeError("ws login failed")
                        await self._sync_subscriptions(conn)
                        await asyncio.gather(
                            login_reader,
                            self._heartbeat_loop(conn, generation),
                            self._resync_loop(conn, generation),
                        )
                    else:
                        await self._sync_subscriptions(conn)
                        await asyncio.gather(
                            self._reader_loop(conn, generation),
                            self._heartbeat_loop(conn, generation),
                            self._resync_loop(conn, generation),
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - 需捕获所有连接期异常以触发重连
                if generation != self._generation:
                    continue
                delay = self._reconnect_policy.delay(attempt)
                logger.warning(
                    f"ws generation={generation} error={exc!r}, reconnect in {delay:.1f}s"
                )
                attempt += 1
                await asyncio.sleep(delay)
            finally:
                if generation == self._generation:
                    self._conn = None

    async def _sync_subscriptions(self, conn: ClientConnection) -> None:
        to_subscribe = self._desired - self._active
        to_unsubscribe = self._active - self._desired
        if to_subscribe:
            await conn.send(
                json.dumps({"op": "subscribe", "args": [c.to_ws_arg() for c in to_subscribe]})
            )
        if to_unsubscribe:
            await conn.send(
                json.dumps({"op": "unsubscribe", "args": [c.to_ws_arg() for c in to_unsubscribe]})
            )
        # 乐观标记为 active；真实的 subscribe/error 事件到达后由 _reader_loop 校正。
        self._active = set(self._desired)

    async def _resync_loop(self, conn: ClientConnection, generation: int) -> None:
        """周期性检查 desired 是否变化（例如新选择了产品），变化则补发订阅指令。"""

        while generation == self._generation:
            await asyncio.sleep(2.0)
            if self._desired != self._active:
                await self._sync_subscriptions(conn)

    async def _reader_loop(self, conn: ClientConnection, generation: int) -> None:
        async for raw in conn:
            if generation != self._generation:
                return
            self._last_message_at = asyncio.get_event_loop().time()
            if raw == "pong":
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"ws non-json message ignored: {raw!r}")
                continue
            if message.get("event") == "login":
                self._login_failed = message.get("code") not in (None, "0", 0)
                self._login_event.set()
                if self._login_failed:
                    logger.warning(f"ws login failed: {message}")
                continue
            if message.get("event") == "error":
                logger.warning(f"ws subscribe error: {message}")
                continue
            await self._on_message(message)

    async def _heartbeat_loop(self, conn: ClientConnection, generation: int) -> None:
        self._last_message_at = asyncio.get_event_loop().time()
        while generation == self._generation:
            await asyncio.sleep(1.0)
            idle = asyncio.get_event_loop().time() - self._last_message_at
            if idle >= self._ping_idle_seconds:
                await conn.send("ping")
                try:
                    await asyncio.wait_for(
                        self._wait_pong(conn, generation), timeout=self._pong_timeout_seconds
                    )
                except TimeoutError:
                    logger.warning(f"ws generation={generation} pong timeout, forcing reconnect")
                    await conn.close()
                    return

    async def _wait_pong(self, conn: ClientConnection, generation: int) -> None:
        # pong 由 _reader_loop 消费（raw == "pong"）；这里只等待 last_message_at 被刷新。
        deadline_start = self._last_message_at
        while self._last_message_at == deadline_start and generation == self._generation:
            await asyncio.sleep(0.2)
