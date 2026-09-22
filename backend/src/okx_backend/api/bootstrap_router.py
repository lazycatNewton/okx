"""GET /api/bootstrap — 前端启动时一次性返回恢复所需的状态。"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from okx_backend.db.base import session_scope
from okx_backend.db.models import AppPreference
from okx_backend.services.economic_calendar import list_economic_calendar
from okx_backend.services.event_contract_catalog import list_event_contract_markets
from okx_backend.services.subscriptions import get_current_selection

router = APIRouter(prefix="/api/bootstrap", tags=["bootstrap"])

SIDEBAR_FIRST_PAGE_SIZE = 50


@router.get("")
async def bootstrap() -> dict:
    ordered_inst_ids = await get_current_selection()
    async with session_scope() as db_session:
        pref = await db_session.scalar(select(AppPreference).where(AppPreference.id == 1))
    last_active = pref.last_active_inst_id if pref else None
    if last_active not in ordered_inst_ids:
        last_active = ordered_inst_ids[0] if ordered_inst_ids else None

    event_markets, _ = await list_event_contract_markets(limit=SIDEBAR_FIRST_PAGE_SIZE)
    calendar_events, _ = await list_economic_calendar(limit=SIDEBAR_FIRST_PAGE_SIZE)

    return {
        "selectedInstIds": ordered_inst_ids,
        "lastActiveInstId": last_active,
        "auxSidebar": {
            "eventContractMarkets": [
                {
                    "seriesId": row.series_id,
                    "eventId": row.event_id,
                    "instId": row.inst_id,
                    "expTime": row.exp_time,
                    "state": row.state,
                    "floorStrike": row.floor_strike,
                    "outcome": row.outcome,
                }
                for row in event_markets
            ],
            "economicCalendar": [
                {
                    "calendarId": row.calendar_id,
                    "date": row.date,
                    "event": row.event,
                    "region": row.region,
                    "importance": row.importance,
                    "actual": row.actual,
                    "forecast": row.forecast,
                }
                for row in calendar_events
            ],
        },
    }
