"""登录 / 退出。

POST /api/session/login：用户名+密码校验，成功建立会话（设置不透明 session cookie）。
DELETE /api/session：立即退出，删除 Redis 会话与 Cookie。
失败仅返回统一的“用户名或密码错误”；连续 5 次失败冻结该用户名登录入口 15 分钟。
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from okx_backend.auth.session import (
    clear_login_failures,
    create_session,
    destroy_session,
    is_login_locked,
    record_login_failure,
)
from okx_backend.config import get_settings
from okx_backend.db.base import session_scope
from okx_backend.db.models import User
from okx_backend.security import generate_session_id, verify_password

router = APIRouter(prefix="/api/session", tags=["session"])
_settings = get_settings()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest, response: Response) -> dict:
    settings = get_settings()

    if await is_login_locked(payload.username):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="登录已被冻结，请稍后重试")

    async with session_scope() as session:
        user = await session.scalar(select(User).where(User.username == payload.username))

    if user is None or not verify_password(payload.password, user.password_hash):
        await record_login_failure(payload.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    await clear_login_failures(payload.username)
    session_id = generate_session_id()
    await create_session(user.id, user.username, session_id)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="strict",
        # 不设置 max_age/expires：关闭浏览器即失效，无空闲超时（会话状态以 Redis 记录为准）。
    )
    return {"username": user.username}


@router.delete("")
async def logout(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=_settings.session_cookie_name),
) -> dict:
    settings = get_settings()
    if session_cookie:
        await destroy_session(session_cookie)
    response.delete_cookie(key=settings.session_cookie_name)
    return {"ok": True}
