"""GET /api/market/{instId}/candles — 已保存的 7 天 K 线时间序列查询。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select

from okx_backend.api.deps import get_current_session
from okx_backend.auth.session import SessionData
from okx_backend.db.base import session_scope
from okx_backend.db.models import Candle, CandleKind

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/{inst_id}/candles")
async def get_candles(
    inst_id: str = Path(...),
    kind: str = Query(default="trade", pattern="^(trade|mark)$"),
    bar: str = Query(...),
    before: int | None = Query(default=None),
    limit: int = Query(default=300, le=300),
    _session: SessionData = Depends(get_current_session),
) -> dict:
    candle_kind = CandleKind.TRADE if kind == "trade" else CandleKind.MARK
    async with session_scope() as session:
        stmt = (
            select(Candle)
            .where(Candle.inst_id == inst_id, Candle.kind == candle_kind, Candle.bar == bar)
            .order_by(Candle.ts_ms.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(Candle.ts_ms < before)
        rows = list((await session.scalars(stmt)).all())
    rows.reverse()
    return {
        "items": [
            {
                "ts": row.ts_ms,
                "o": row.o,
                "h": row.h,
                "l": row.low,
                "c": row.c,
                "vol": row.vol,
                "volCcy": row.vol_ccy,
                "volCcyQuote": row.vol_ccy_quote,
                "confirm": row.confirm,
            }
            for row in rows
        ]
    }
