"""GET /api/products — 产品发现结果查询（现货/永续，含所有 state）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from okx_backend.api.deps import get_current_session
from okx_backend.auth.session import SessionData
from okx_backend.services.catalog import list_current_instruments

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("")
async def list_products(
    _session: SessionData = Depends(get_current_session),
    inst_type: str | None = Query(default=None, alias="instType"),
    state: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> dict:
    rows = await list_current_instruments(inst_type=inst_type, state=state, query=q)
    return {
        "items": [
            {
                "instType": row.inst_type,
                "instId": row.inst_id,
                "state": row.state,
                "baseCcy": row.base_ccy,
                "quoteCcy": row.quote_ccy,
                "settleCcy": row.settle_ccy,
                "ctType": row.ct_type,
                "instFamily": row.inst_family,
                "selectable": row.state == "live",
            }
            for row in rows
        ]
    }
