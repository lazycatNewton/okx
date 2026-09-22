"""FastAPI 依赖：从 Cookie 解析当前会话与用户。"""

from __future__ import annotations

from fastapi import Cookie, HTTPException, status

from okx_backend.auth.session import SessionData, get_session
from okx_backend.config import get_settings

_settings = get_settings()


async def get_current_session(
    session_cookie: str | None = Cookie(default=None, alias=_settings.session_cookie_name),
) -> SessionData:
    if session_cookie is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="未登录")
    session = await get_session(session_cookie)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="会话已失效")
    return session
