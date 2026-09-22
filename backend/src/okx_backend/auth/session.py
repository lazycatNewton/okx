"""会话管理：登录、退出、当前用户校验、登录失败冻结。

依据 okx-requirements.md「前端形态与使用范围」：
- 会话只在当前浏览器会话有效；关闭浏览器失效（依赖非持久化 Cookie，不设置 Max-Age/Expires）；
  无空闲超时；主动退出立即失效。
- 新浏览器登录使旧会话失效（单会话槽位：Redis 中每用户只保留一个当前有效 session_id）。
- 连续 5 次失败冻结登录入口 15 分钟；冻结不影响已建立会话或后台采集。
- 会话状态存 Redis；不透明 session id 作为 Cookie 值。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from okx_backend.cache import get_redis
from okx_backend.config import get_settings

_SESSION_KEY = "session:{session_id}"
_USER_CURRENT_SESSION_KEY = "session:current:{user_id}"
_LOGIN_FAIL_KEY = "login:fail:{username}"
_LOGIN_LOCK_KEY = "login:lock:{username}"


@dataclass(frozen=True)
class SessionData:
    user_id: int
    username: str
    created_at: float


async def is_login_locked(username: str) -> bool:
    redis = get_redis()
    return bool(await redis.get(_LOGIN_LOCK_KEY.format(username=username)))


async def record_login_failure(username: str) -> None:
    settings = get_settings()
    redis = get_redis()
    key = _LOGIN_FAIL_KEY.format(username=username)
    count = await redis.incr(key)
    await redis.expire(key, settings.login_lockout_seconds)
    if count >= settings.login_lockout_threshold:
        await redis.set(
            _LOGIN_LOCK_KEY.format(username=username), "1", ex=settings.login_lockout_seconds
        )
        await redis.delete(key)


async def clear_login_failures(username: str) -> None:
    redis = get_redis()
    await redis.delete(_LOGIN_FAIL_KEY.format(username=username))


async def create_session(user_id: int, username: str, session_id: str) -> None:
    """建立新会话，并使该用户此前的任何会话（如有）立即失效（单会话槽位）。"""

    settings = get_settings()
    redis = get_redis()

    previous = await redis.get(_USER_CURRENT_SESSION_KEY.format(user_id=user_id))
    if previous:
        await redis.delete(_SESSION_KEY.format(session_id=previous))

    payload = json.dumps({"user_id": user_id, "username": username, "created_at": time.time()})
    await redis.set(
        _SESSION_KEY.format(session_id=session_id), payload, ex=settings.session_ttl_seconds
    )
    await redis.set(
        _USER_CURRENT_SESSION_KEY.format(user_id=user_id),
        session_id,
        ex=settings.session_ttl_seconds,
    )


async def get_session(session_id: str) -> SessionData | None:
    redis = get_redis()
    raw = await redis.get(_SESSION_KEY.format(session_id=session_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return SessionData(
        user_id=data["user_id"], username=data["username"], created_at=data["created_at"]
    )


async def destroy_session(session_id: str) -> None:
    """主动退出：立即删除 Redis 会话记录（Cookie 由路由层一并清除）。"""

    redis = get_redis()
    raw = await redis.get(_SESSION_KEY.format(session_id=session_id))
    if raw:
        data = json.loads(raw)
        user_id = data["user_id"]
        current = await redis.get(_USER_CURRENT_SESSION_KEY.format(user_id=user_id))
        if current == session_id:
            await redis.delete(_USER_CURRENT_SESSION_KEY.format(user_id=user_id))
    await redis.delete(_SESSION_KEY.format(session_id=session_id))
