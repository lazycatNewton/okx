"""浏览器 WS 发送端关闭时的回归测试。"""

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from okx_backend.api.ws_app_router import run_socket_loops, try_send_text


@pytest.mark.asyncio
async def test_try_send_text_treats_client_disconnect_as_normal_shutdown() -> None:
    class ClosingSocket:
        async def send_text(self, _message: str) -> None:
            raise WebSocketDisconnect(code=1006)

    assert await try_send_text(ClosingSocket(), "message") is False


@pytest.mark.asyncio
async def test_run_socket_loops_cancels_receiver_when_sender_disconnects_first() -> None:
    """回归测试：修复前，sender 先结束后 receiver 会在下一次 receive_text() 上
    抛出 `RuntimeError('WebSocket is not connected...')`（而非 WebSocketDisconnect），
    冒泡成未处理的 ASGI 异常。现在 sender 结束应立即取消 receiver，不再触发该异常。
    """

    receiver_cancelled = asyncio.Event()

    async def sender() -> None:
        return None  # 模拟发送端检测到断开后立即正常退出

    async def receiver() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            receiver_cancelled.set()
            raise

    await asyncio.wait_for(run_socket_loops(receiver(), sender()), timeout=1)
    assert receiver_cancelled.is_set()


@pytest.mark.asyncio
async def test_run_socket_loops_swallows_normal_receiver_disconnect() -> None:
    async def sender() -> None:
        await asyncio.sleep(10)

    async def receiver() -> None:
        raise WebSocketDisconnect(code=1000)

    await asyncio.wait_for(run_socket_loops(receiver(), sender()), timeout=1)
