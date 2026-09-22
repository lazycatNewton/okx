"""M23 经济日历：共享辅助数据，需登录鉴权，未配置凭证/鉴权失败/网络故障/未达 VIP1 时返回空。

依据 okx-requirements.md「M23」：
- REST `GET /api/v5/public/economic-calendar`：需鉴权，限速 1 次/5 秒/IP，按 `date` 分页。
- WS `economic-calendar`（business，需登录）：持续实时来源，每 30 分钟以 REST 补充。
- 未配置凭证、鉴权失败、网络故障或账户不满足 VIP1（OKX 返回特定错误码）时，
  应用统一返回空数据集，不暴露错误详情、不影响其他行情连接。
"""

from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from okx_backend.config import get_settings
from okx_backend.db.base import session_scope
from okx_backend.db.models import EconomicCalendarEvent
from okx_backend.okx_client.auth import build_rest_auth_headers, build_ws_login_args
from okx_backend.okx_client.rest import OkxRestClient
from okx_backend.okx_client.ws_client import ChannelArg, OkxWsClient

REST_PATH = "/api/v5/public/economic-calendar"
REST_PAGE_LIMIT = 100
_REST_PACING_SECONDS = 5.1  # 限速 1 次/5s/IP，留出安全余量
RESYNC_INTERVAL_SECONDS = 1800.0  # 需求文档：每 30 分钟以 REST 补充


def credentials_configured() -> bool:
    settings = get_settings()
    return bool(settings.okx_api_key and settings.okx_api_secret and settings.okx_api_passphrase)


def _to_optional_int(value: str | None) -> int | None:
    return int(value) if value else None


async def _authed_get_calendar(client: OkxRestClient, before: str | None) -> list[dict]:
    settings = get_settings()
    headers = build_rest_auth_headers(
        settings.okx_api_key or "",
        settings.okx_api_secret or "",
        settings.okx_api_passphrase or "",
        "GET",
        REST_PATH,
    )
    return await client.get_economic_calendar(
        before=before, limit=REST_PAGE_LIMIT, signed_headers=headers
    )


async def _store_calendar_row(row: dict) -> None:
    calendar_id = row.get("calendarId")
    if calendar_id is None:
        logger.warning(f"economic-calendar row missing calendarId: {row!r}")
        return
    ts_ms = int(row.get("uTime") or row.get("ts") or row.get("date") or 0)
    async with session_scope() as session:
        stmt = mysql_insert(EconomicCalendarEvent).values(
            calendar_id=calendar_id,
            date=_to_optional_int(row.get("date")),
            ts_ms=ts_ms,
            event=row.get("event"),
            region=row.get("region"),
            importance=row.get("importance"),
            actual=row.get("actual"),
            forecast=row.get("forecast"),
            previous=row.get("previous"),
            raw_payload=row,
        ).on_duplicate_key_update(raw_payload=row)
        await session.execute(stmt)


async def refresh_economic_calendar() -> int:
    """未配置凭证时立即返回 0，不发起请求；鉴权失败/网络故障/非 VIP1 时捕获异常返回 0，
    不暴露错误详情、不影响调用方（保留最近有效数据，下一周期重试）。
    """

    if not credentials_configured():
        return 0
    saved = 0
    try:
        async with OkxRestClient() as client:
            before: str | None = None
            while True:
                rows = await _authed_get_calendar(client, before)
                if not rows:
                    return saved
                for row in rows:
                    await _store_calendar_row(row)
                    saved += 1
                if len(rows) < REST_PAGE_LIMIT:
                    return saved
                oldest_date = min(_to_optional_int(row.get("date")) or 0 for row in rows)
                before = str(oldest_date)
                await asyncio.sleep(_REST_PACING_SECONDS)
    except Exception as exc:  # noqa: BLE001 - 需求文档：鉴权失败/网络故障均返回空，不暴露细节
        logger.warning(f"economic-calendar refresh failed, returning empty per spec: {exc!r}")
        return saved


async def run_economic_calendar_resync_forever() -> None:
    """后台常驻任务：每 30 分钟以 REST 补充；未配置凭证时不发起任何请求，只空转等待。"""

    while True:
        await asyncio.sleep(RESYNC_INTERVAL_SECONDS)
        try:
            await refresh_economic_calendar()
        except Exception as exc:  # noqa: BLE001 - 单轮失败不应影响下一轮或其他行情连接
            logger.error(f"economic-calendar resync failed: {exc!r}")


def start_economic_calendar_ws() -> OkxWsClient | None:
    """未配置凭证时返回 `None`（不建立连接）；否则返回已声明订阅但未 `start()` 的客户端，
    调用方负责启动/停止。`OkxWsClient` 在每次（重）连接时都会调用 `login_args_provider()`
    实时生成签名（时间戳必须是当次连接发起时刻，不能复用旧连接的签名）；登录失败
    （含非 VIP1）会被 `OkxWsClient` 当作连接异常触发标准指数退避重连，不会无限轰炸，
    符合"鉴权失败返回空数据集、不影响其他行情连接"的要求——空数据集体现在
    `list_economic_calendar()` 读到的仍是登录成功前已有的（可能为空的）本地数据。
    """

    if not credentials_configured():
        return None
    settings = get_settings()

    def _login_args_provider() -> list[dict]:
        return build_ws_login_args(
            settings.okx_api_key or "",
            settings.okx_api_secret or "",
            settings.okx_api_passphrase or "",
        )

    client = OkxWsClient(
        settings.okx_ws_business,
        _on_economic_calendar_message,
        login_args_provider=_login_args_provider,
    )
    client.set_desired_channels({ChannelArg(channel="economic-calendar")})
    return client


async def _on_economic_calendar_message(message: dict) -> None:
    arg = message.get("arg", {})
    if arg.get("channel") != "economic-calendar":
        return
    for row in message.get("data", []):
        await _store_calendar_row(row)


async def list_economic_calendar(
    before_date: int | None = None, limit: int = 50
) -> tuple[list[EconomicCalendarEvent], bool]:
    """本地目录查询：按 `date` 倒序分页；未配置凭证等场景下表内本就没有数据，
    自然返回空列表，符合"应用返回空数据集"的要求，不需要额外的特判分支。
    """

    async with session_scope() as session:
        stmt = select(EconomicCalendarEvent).order_by(
            EconomicCalendarEvent.date.desc()
        ).limit(limit + 1)
        if before_date is not None:
            stmt = stmt.where(EconomicCalendarEvent.date < before_date)
        rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > limit
    return rows[:limit], has_more
