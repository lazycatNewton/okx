"""GET /api/aux/event-contract-markets 与 GET /api/aux/economic-calendar。

依据 okx-requirements.md「浏览器 HTTP 接口」：
- 均使用不透明 `cursor` 分页，响应包含 `items`、`nextCursor`、`hasMore`。
- M22 按 `expTime` 倒序；M23 按 `date` 倒序；M23 不可用时返回空 `items`（`nextCursor=null`,
  `hasMore=false`，不暴露内部原因）。
- `cursor` 不透明：本实现用条目自身的排序字段值（`expTime`/`date`）编码，调用方不应
  假定其内部结构，只需原样传回上一页响应的 `nextCursor`。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from okx_backend.services.economic_calendar import list_economic_calendar
from okx_backend.services.event_contract_catalog import list_event_contract_markets

router = APIRouter(prefix="/api/aux", tags=["aux"])

PAGE_SIZE = 50


@router.get("/event-contract-markets")
async def get_event_contract_markets(cursor: str | None = Query(default=None)) -> dict:
    before_exp_time = int(cursor) if cursor is not None else None
    rows, has_more = await list_event_contract_markets(before_exp_time, limit=PAGE_SIZE)
    next_cursor = str(rows[-1].exp_time) if rows and has_more else None
    return {
        "items": [
            {
                "seriesId": row.series_id,
                "eventId": row.event_id,
                "instId": row.inst_id,
                "expTime": row.exp_time,
                "state": row.state,
                "floorStrike": row.floor_strike,
                "outcome": row.outcome,
                "category": row.raw_payload.get("category"),
                "listTime": row.list_time,
                "fixTime": row.fix_time,
                "capStrike": row.cap_strike,
                "settleValue": row.settle_value,
                "disputed": row.disputed,
                "hitDir": row.hit_dir,
            }
            for row in rows
        ],
        "nextCursor": next_cursor,
        "hasMore": has_more,
    }


@router.get("/economic-calendar")
async def get_economic_calendar_sidebar(cursor: str | None = Query(default=None)) -> dict:
    before_date = int(cursor) if cursor is not None else None
    rows, has_more = await list_economic_calendar(before_date, limit=PAGE_SIZE)
    next_cursor = str(rows[-1].date) if rows and has_more and rows[-1].date is not None else None
    return {
        "items": [
            {
                "calendarId": row.calendar_id,
                "date": row.date,
                "event": row.event,
                "region": row.region,
                "importance": row.importance,
                "actual": row.actual,
                "forecast": row.forecast,
                "previous": row.previous,
                "category": row.raw_payload.get("category"),
                "prevInitial": row.raw_payload.get("prevInitial"),
                "refDate": row.raw_payload.get("refDate"),
                "unit": row.raw_payload.get("unit"),
                "ccy": row.raw_payload.get("ccy"),
                "uTime": row.raw_payload.get("uTime"),
            }
            for row in rows
        ],
        "nextCursor": next_cursor,
        "hasMore": has_more,
    }
