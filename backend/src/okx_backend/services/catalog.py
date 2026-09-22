"""产品目录：自动发现（SPOT/SWAP）+ 永久版本化保存。

依据 okx-requirements.md「产品发现与订阅选择」：
- 分别调用 GET /api/v5/public/instruments?instType=SPOT|SWAP。
- 发现结果本身不建立订阅，也不扩大产品范围；只有用户选中的 instId 才进入采集集合。
- 同一产品的基础字段或 state 变化时追加新版本；不物理删除已下线产品。
- 只有 state=live 的产品可被选择。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update

from okx_backend.db.base import session_scope
from okx_backend.db.models import InstrumentCatalogVersion
from okx_backend.okx_client.rest import OkxRestClient

DISCOVERABLE_INST_TYPES = ("SPOT", "SWAP")

_TRACKED_FIELDS = ("state", "base_ccy", "quote_ccy", "settle_ccy", "ct_type", "inst_family", "uly")


@dataclass(frozen=True)
class InstrumentRow:
    inst_type: str
    inst_id: str
    state: str
    base_ccy: str | None
    quote_ccy: str | None
    settle_ccy: str | None
    ct_type: str | None
    inst_family: str | None
    uly: str | None
    raw_payload: dict


def _to_row(inst_type: str, raw: dict) -> InstrumentRow:
    return InstrumentRow(
        inst_type=inst_type,
        inst_id=raw["instId"],
        state=raw.get("state", ""),
        base_ccy=raw.get("baseCcy") or None,
        quote_ccy=raw.get("quoteCcy") or None,
        settle_ccy=raw.get("settleCcy") or None,
        ct_type=raw.get("ctType") or None,
        inst_family=raw.get("instFamily") or None,
        uly=raw.get("uly") or None,
        raw_payload=raw,
    )


async def refresh_catalog() -> int:
    """调用 REST 刷新 SPOT/SWAP 目录；返回本次追加的新版本数量。

    限速依据：20 次/2s，按 IP + Instrument Type（两次调用，各自独立计数）。
    """

    appended = 0
    async with OkxRestClient() as client:
        for inst_type in DISCOVERABLE_INST_TYPES:
            raws = await client.get_instruments(inst_type)
            rows = [_to_row(inst_type, raw) for raw in raws]
            appended += await _apply_rows(rows)
    return appended


async def _apply_rows(rows: list[InstrumentRow]) -> int:
    appended = 0
    async with session_scope() as session:
        for row in rows:
            current = await session.scalar(
                select(InstrumentCatalogVersion).where(
                    InstrumentCatalogVersion.inst_type == row.inst_type,
                    InstrumentCatalogVersion.inst_id == row.inst_id,
                    InstrumentCatalogVersion.is_current.is_(True),
                )
            )
            if current is not None and all(
                getattr(current, field) == getattr(row, field) for field in _TRACKED_FIELDS
            ):
                continue  # 基础字段与 state 均未变化，不追加新版本
            if current is not None:
                await session.execute(
                    update(InstrumentCatalogVersion)
                    .where(InstrumentCatalogVersion.id == current.id)
                    .values(is_current=False)
                )
            session.add(
                InstrumentCatalogVersion(
                    inst_type=row.inst_type,
                    inst_id=row.inst_id,
                    state=row.state,
                    base_ccy=row.base_ccy,
                    quote_ccy=row.quote_ccy,
                    settle_ccy=row.settle_ccy,
                    ct_type=row.ct_type,
                    inst_family=row.inst_family,
                    uly=row.uly,
                    raw_payload=row.raw_payload,
                    is_current=True,
                )
            )
            appended += 1
    return appended


async def list_current_instruments(
    inst_type: str | None = None, state: str | None = None, query: str | None = None
) -> list[InstrumentCatalogVersion]:
    async with session_scope() as session:
        stmt = select(InstrumentCatalogVersion).where(InstrumentCatalogVersion.is_current.is_(True))
        if inst_type:
            stmt = stmt.where(InstrumentCatalogVersion.inst_type == inst_type)
        if state:
            stmt = stmt.where(InstrumentCatalogVersion.state == state)
        if query:
            stmt = stmt.where(InstrumentCatalogVersion.inst_id.like(f"%{query.upper()}%"))
        result = await session.scalars(stmt)
        return list(result.all())


async def get_current_instrument(inst_id: str) -> InstrumentCatalogVersion | None:
    async with session_scope() as session:
        return await session.scalar(
            select(InstrumentCatalogVersion).where(
                InstrumentCatalogVersion.inst_id == inst_id,
                InstrumentCatalogVersion.is_current.is_(True),
            )
        )
