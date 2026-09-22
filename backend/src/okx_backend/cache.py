"""Redis 客户端：仅用于可重建的最新状态缓存与会话存储，不作为永久数据来源。"""

from __future__ import annotations

from redis.asyncio import Redis

from okx_backend.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
