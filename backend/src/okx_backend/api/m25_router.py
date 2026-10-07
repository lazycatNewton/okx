"""GET /api/market/{instId}/m25/{metric} — 已保存的 M25 统计历史查询。

依据 okx-requirements.md：每个 Tab 仅显示其 instId 对应的 S01/S04/S05。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import select

from okx_backend.db.base import session_scope
from okx_backend.db.models import M25Metric, M25Stat
from okx_backend.services.m25_stats import OKX_STAT_MAX_ROWS

router = APIRouter(prefix="/api/market", tags=["m25"])


@router.get("/{inst_id}/m25/{metric}")
async def get_m25_stat(
    inst_id: str = Path(...),
    metric: str = Path(...),
    period: str | None = Query(default=None),
    unit: str | None = Query(default=None),
    before: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=OKX_STAT_MAX_ROWS),
) -> dict:
    """`inst_id` 为查询维度：S01/S04/S05 均使用永续 instId。"""

    try:
        metric_enum = M25Metric(metric)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"未知指标: {metric}") from exc

    async with session_scope() as session:
        stmt = (
            select(M25Stat)
            .where(M25Stat.metric == metric_enum, M25Stat.query_key == inst_id)
            .order_by(M25Stat.ts_ms.desc())
            .limit(limit)
        )
        if period is not None:
            stmt = stmt.where(M25Stat.period == period)
        if unit is not None:
            stmt = stmt.where(M25Stat.unit == unit)
        if before is not None:
            stmt = stmt.where(M25Stat.ts_ms < before)
        rows = list((await session.scalars(stmt)).all())
    rows.reverse()
    return {
        "items": [
            # `row.raw_payload` 自身也带一个字符串 `ts` 键
            # （如 `{"ts": "170...", ...}`），必须放在前面被覆盖，否则展开顺序会让
            # 权威的整数 `row.ts_ms` 被字符串覆盖，前端 `new Date(字符串)` 解析失败。
            {**row.raw_payload, "ts": row.ts_ms, "period": row.period, "unit": row.unit}
            for row in rows
        ]
    }
