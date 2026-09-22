"""M22 事件合约辅助市场：系列/事件/市场三级目录（永久）+ WS 状态更新（7 天）。

依据 okx-requirements.md「M22：事件合约辅助市场」：
- 保留全球站自动发现的全部预测市场，不按 category/seriesId/eventId/state 筛选。
- 通过 3 个 REST 接口建立完整层级：series -> events(seriesId) -> markets(seriesId)。
- 实时更新用 public WS `event-contract-markets`（`instType=EVENTS`），不推送初始快照，
  REST 结果是初始状态的唯一来源；持续以 WS 为实时来源，并每小时以 REST 完整校正目录。
- WS 更新按 `instId + 业务时间 + payload 哈希` 追加为 7 天修订事件（`EventContractRevision`），
  同时原地更新 `EventContractMarket` 当前状态（属于永久目录，不参与 7 天清理）。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from okx_backend.config import get_settings
from okx_backend.db.base import session_scope
from okx_backend.db.models import (
    EventContractEvent,
    EventContractMarket,
    EventContractRevision,
    EventContractSeries,
)
from okx_backend.okx_client.rest import OkxRestClient
from okx_backend.okx_client.ws_client import ChannelArg, OkxWsClient

REST_PAGE_LIMIT = 100
_REST_PACING_SECONDS = 0.25  # 10 次/2s/IP 限速下的安全请求间隔
CATALOG_RESYNC_SECONDS = 3600.0  # 需求文档：每小时以 REST 完整校正目录


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _to_optional_int(value: Any) -> int | None:
    return int(value) if value not in (None, "") else None


async def _fetch_all_events(client: OkxRestClient, series_id: str) -> list[dict[str, Any]]:
    """按 `expTime` 用 `before` 递减分页，直至拿到全部事件（不按 state 过滤）。"""

    items: list[dict[str, Any]] = []
    before: str | None = None
    while True:
        await asyncio.sleep(_REST_PACING_SECONDS)
        page = await client.get_event_contract_events(
            series_id, before=before, limit=REST_PAGE_LIMIT
        )
        if not page:
            return items
        items.extend(page)
        if len(page) < REST_PAGE_LIMIT:
            return items
        oldest_exp = min(_to_optional_int(row.get("expTime")) or 0 for row in page)
        before = str(oldest_exp)


async def _fetch_all_markets(client: OkxRestClient, series_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    before: str | None = None
    while True:
        await asyncio.sleep(_REST_PACING_SECONDS)
        page = await client.get_event_contract_markets(
            series_id, before=before, limit=REST_PAGE_LIMIT
        )
        if not page:
            return items
        items.extend(page)
        if len(page) < REST_PAGE_LIMIT:
            return items
        oldest_exp = min(_to_optional_int(row.get("expTime")) or 0 for row in page)
        before = str(oldest_exp)


async def refresh_event_contract_catalog() -> dict[str, int]:
    """全量刷新系列/事件/市场三级目录；用于首次启动初始化和每小时 REST 校正。

    返回各层级写入行数（用于日志观测，upsert 语义下不代表新增数量）。
    """

    counts = {"series": 0, "events": 0, "markets": 0}
    async with OkxRestClient() as client:
        series_rows = await client.get_event_contract_series()
        async with session_scope() as session:
            for row in series_rows:
                stmt = mysql_insert(EventContractSeries).values(
                    series_id=row["seriesId"],
                    title=row.get("title"),
                    category=row.get("category"),
                    freq=row.get("freq"),
                    settlement=row.get("settlement"),
                    raw_payload=row,
                ).on_duplicate_key_update(
                    title=row.get("title"), category=row.get("category"),
                    freq=row.get("freq"), settlement=row.get("settlement"), raw_payload=row,
                )
                await session.execute(stmt)
                counts["series"] += 1

        for row in series_rows:
            series_id = row["seriesId"]
            events = await _fetch_all_events(client, series_id)
            markets = await _fetch_all_markets(client, series_id)
            async with session_scope() as session:
                for event in events:
                    stmt = mysql_insert(EventContractEvent).values(
                        event_id=event["eventId"],
                        series_id=series_id,
                        exp_time=_to_optional_int(event.get("expTime")),
                        state=event.get("state"),
                        raw_payload=event,
                    ).on_duplicate_key_update(
                        exp_time=_to_optional_int(event.get("expTime")),
                        state=event.get("state"), raw_payload=event,
                    )
                    await session.execute(stmt)
                    counts["events"] += 1
                for market in markets:
                    stmt = mysql_insert(EventContractMarket).values(
                        inst_id=market["instId"],
                        event_id=market["eventId"],
                        series_id=series_id,
                        list_time=_to_optional_int(market.get("listTime")),
                        fix_time=_to_optional_int(market.get("fixTime")),
                        exp_time=_to_optional_int(market.get("expTime")),
                        state=market.get("state"),
                        outcome=market.get("outcome"),
                        floor_strike=market.get("floorStrike"),
                        cap_strike=market.get("capStrike"),
                        settle_value=market.get("settleValue"),
                        disputed=str(market.get("disputed")),
                        hit_dir=market.get("hitDir"),
                        raw_payload=market,
                    ).on_duplicate_key_update(
                        list_time=_to_optional_int(market.get("listTime")),
                        fix_time=_to_optional_int(market.get("fixTime")),
                        exp_time=_to_optional_int(market.get("expTime")),
                        state=market.get("state"), outcome=market.get("outcome"),
                        floor_strike=market.get("floorStrike"),
                        cap_strike=market.get("capStrike"),
                        settle_value=market.get("settleValue"),
                        disputed=str(market.get("disputed")), hit_dir=market.get("hitDir"),
                        raw_payload=market,
                    )
                    await session.execute(stmt)
                    counts["markets"] += 1

    logger.info(f"event-contract catalog refreshed: {counts}")
    return counts


async def apply_event_contract_ws_update(row: dict[str, Any]) -> None:
    """处理 `event-contract-markets` WS 推送的单条状态更新：

    1) 原地更新 `EventContractMarket` 当前状态（永久目录，不受 7 天清理影响）；
    2) 追加一条 `EventContractRevision` 修订事件（7 天滚动保留，按
       `inst_id + business_ts + payload_hash` 去重完全重复的重发）。

    WS 只推送状态变更，不保证市场先前已存在于本地目录（例如服务重启窗口内新上线的
    市场）；若本地无对应 `event_id`/`series_id` 记录，跳过市场表 upsert 但仍记录修订
    事件，避免因外键缺失报错吞掉整条推送。
    """

    inst_id = row.get("instId")
    if inst_id is None:
        logger.warning(f"event-contract-markets row missing instId: {row!r}")
        return
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    payload_hash = _payload_hash(row)

    async with session_scope() as session:
        existing = await session.scalar(
            select(EventContractMarket).where(EventContractMarket.inst_id == inst_id)
        )
        if existing is not None:
            stmt = mysql_insert(EventContractMarket).values(
                inst_id=inst_id,
                event_id=row.get("eventId", existing.event_id),
                series_id=row.get("seriesId", existing.series_id),
                list_time=_to_optional_int(row.get("listTime")) or existing.list_time,
                fix_time=_to_optional_int(row.get("fixTime")),
                exp_time=_to_optional_int(row.get("expTime")),
                state=row.get("state"),
                outcome=row.get("outcome"),
                floor_strike=row.get("floorStrike"),
                cap_strike=row.get("capStrike"),
                settle_value=row.get("settleValue"),
                disputed=str(row.get("disputed")),
                hit_dir=row.get("hitDir"),
                raw_payload=row,
            ).on_duplicate_key_update(
                fix_time=_to_optional_int(row.get("fixTime")),
                exp_time=_to_optional_int(row.get("expTime")),
                state=row.get("state"), outcome=row.get("outcome"),
                floor_strike=row.get("floorStrike"), cap_strike=row.get("capStrike"),
                settle_value=row.get("settleValue"), disputed=str(row.get("disputed")),
                hit_dir=row.get("hitDir"), raw_payload=row,
            )
            await session.execute(stmt)
        else:
            logger.warning(
                f"event-contract-markets update for unknown instId={inst_id}, "
                "recording revision only (catalog will self-heal on next hourly resync)"
            )

        revision_stmt = mysql_insert(EventContractRevision).values(
            inst_id=inst_id, business_ts=now_ms, payload_hash=payload_hash, raw_payload=row,
        ).on_duplicate_key_update(raw_payload=row)
        await session.execute(revision_stmt)


async def run_event_contract_hourly_resync() -> None:
    """后台常驻任务：每小时以 REST 完整校正目录；单轮失败记录日志后继续下一轮。"""

    while True:
        await asyncio.sleep(CATALOG_RESYNC_SECONDS)
        try:
            await refresh_event_contract_catalog()
        except Exception as exc:  # noqa: BLE001 - 校正失败不应影响 WS 实时更新
            logger.error(f"event-contract hourly resync failed: {exc!r}")


def start_event_contract_ws() -> OkxWsClient:
    """独立于产品采集器的 public WS 连接，固定订阅 `event-contract-markets`，
    不随用户已选产品变化（M22 是全局共享辅助数据，不属于任何单一产品）。

    调用方负责生命周期管理：`client.start()` 后台跑，退出时 `await client.stop()`。
    """

    settings = get_settings()
    client = OkxWsClient(settings.okx_ws_public, _on_event_contract_message)
    client.set_desired_channels({ChannelArg(channel="event-contract-markets", inst_type="EVENTS")})
    return client


async def _on_event_contract_message(message: dict) -> None:
    arg = message.get("arg", {})
    if arg.get("channel") != "event-contract-markets":
        return
    for row in message.get("data", []):
        await apply_event_contract_ws_update(row)


async def list_event_contract_markets(
    before_exp_time: int | None = None, limit: int = 50
) -> tuple[list[EventContractMarket], bool]:
    """本地目录查询：按 `expTime` 倒序分页，供 `/api/aux/event-contract-markets` 使用。

    返回 `(items, has_more)`；`items` 长度为 `limit`（不足则为实际数量）。
    """

    async with session_scope() as session:
        stmt = select(EventContractMarket).order_by(EventContractMarket.exp_time.desc()).limit(
            limit + 1
        )
        if before_exp_time is not None:
            stmt = stmt.where(EventContractMarket.exp_time < before_exp_time)
        rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > limit
    return rows[:limit], has_more
