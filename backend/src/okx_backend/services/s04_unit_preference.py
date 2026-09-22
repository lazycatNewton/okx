"""M25 S04 单位偏好：每个产品最近一次选择的 `unit`（0/1/2），永久保存，默认 `1`。

依据 okx-requirements.md：单用户产品，偏好只按 `inst_id` 保存（沿用初始 schema
`M25UnitPreference` 表，不新增按 user_id 拆分的表）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from okx_backend.db.base import session_scope
from okx_backend.db.models import M25UnitPreference

DEFAULT_UNIT = "1"


async def get_s04_unit(inst_id: str) -> str:
    async with session_scope() as session:
        row = await session.scalar(
            select(M25UnitPreference).where(M25UnitPreference.inst_id == inst_id)
        )
        return row.unit if row is not None else DEFAULT_UNIT


async def set_s04_unit(inst_id: str, unit: str) -> None:
    async with session_scope() as session:
        stmt = mysql_insert(M25UnitPreference).values(
            inst_id=inst_id, unit=unit
        ).on_duplicate_key_update(unit=unit)
        await session.execute(stmt)
