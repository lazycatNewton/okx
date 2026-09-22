"""浏览器实时 WebSocket：/ws/app。

协议依据 okx-requirements.md「本产品接口契约」：
- 客户端消息：{"type": "activate-product"|"deactivate-product", "instId": "..."}
- 服务端消息：{"type", "instId", "channel", "data", "sourceTs", "receivedAt"}
  type in {snapshot, update, empty}。
无登录：不做鉴权，直接接受连接。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from okx_backend.realtime.hub import BrowserConnection, RealtimeHub, get_hub

router = APIRouter()


async def try_send_text(websocket: WebSocket, message: str) -> bool:
    """客户端在队列等待期间关闭连接是正常竞争条件，不应变成 ASGI 异常。"""

    try:
        await websocket.send_text(message)
    except WebSocketDisconnect:
        return False
    return True


async def run_socket_loops(
    receiver: Coroutine[Any, Any, None], sender: Coroutine[Any, Any, None]
) -> None:
    """并发运行收发循环；任一方先检测到断开，立即取消另一方并统一清理。

    发送端和接收端各自独立调用 Starlette 的 send/receive；一旦某一侧因客户端断开
    而结束（send 失败或 receive 收到断开），Starlette 会把 `application_state`
    标记为 DISCONNECTED。若不取消另一侧，它下一次调用 receive_text()/send_text()
    会因状态已经是 DISCONNECTED 而抛出 RuntimeError（而不是 WebSocketDisconnect），
    变成未处理的 ASGI 异常。因此这里用 FIRST_COMPLETED 保证只处理一次断开事件。
    """

    receiver_task = asyncio.create_task(receiver)
    sender_task = asyncio.create_task(sender)
    tasks = {receiver_task, sender_task}
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                raise exc
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _receive_loop(websocket: WebSocket, hub: RealtimeHub, conn: BrowserConnection) -> None:
    while True:
        raw = await websocket.receive_text()
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msg_type = message.get("type")
        inst_id = message.get("instId")
        if msg_type == "activate-product" and inst_id:
            await hub.activate(conn, inst_id)
        elif msg_type == "deactivate-product" and inst_id:
            hub.deactivate(conn, inst_id)


async def _send_loop(websocket: WebSocket, conn: BrowserConnection) -> None:
    while True:
        message = await conn.queue.get()
        if not await try_send_text(websocket, message):
            return


@router.websocket("/ws/app")
async def ws_app(websocket: WebSocket) -> None:
    await websocket.accept()
    hub = get_hub()
    conn = hub.register()
    try:
        await run_socket_loops(
            _receive_loop(websocket, hub, conn), _send_loop(websocket, conn)
        )
    finally:
        hub.unregister(conn)
