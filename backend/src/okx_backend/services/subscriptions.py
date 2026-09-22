"""订阅配置：单例永久全局产品选择（无登录，全应用共享一份配置）。

依据 okx-requirements.md「产品发现与订阅选择」「数据视图与产品面板」：
- 产品选择使用有序 instId 列表，原子保存为永久全局配置；拒绝非 live 的 instId。
- 已选产品变为非 live 时，配置仍保留该 instId（不静默丢弃），前端据此关闭 Tab；
  恢复 live 后 Tab 自动恢复——因此这里“持久化选择”与“当前可采集的 live 子集”是两回事。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update

from okx_backend.db.base import session_scope
from okx_backend.db.models import InstrumentCatalogVersion, SubscriptionConfigVersion


@dataclass(frozen=True)
class SubscriptionUpdateResult:
    accepted: list[str]
    rejected: list[str]  # 非 live 或不存在的 instId


async def get_current_selection() -> list[str]:
    async with session_scope() as session:
        current = await session.scalar(
            select(SubscriptionConfigVersion)
            .where(SubscriptionConfigVersion.is_current.is_(True))
            .order_by(SubscriptionConfigVersion.id.desc())
        )
        return list(current.ordered_inst_ids) if current else []


async def set_selection(ordered_inst_ids: list[str]) -> SubscriptionUpdateResult:
    """原子保存新的有序选择；只有 state=live 的 instId 被接受，其余记为 rejected 并被剔除。"""

    async with session_scope() as session:
        accepted: list[str] = []
        rejected: list[str] = []
        for inst_id in ordered_inst_ids:
            inst = await session.scalar(
                select(InstrumentCatalogVersion).where(
                    InstrumentCatalogVersion.inst_id == inst_id,
                    InstrumentCatalogVersion.is_current.is_(True),
                )
            )
            if inst is not None and inst.state == "live":
                accepted.append(inst_id)
            else:
                rejected.append(inst_id)

        await session.execute(
            update(SubscriptionConfigVersion)
            .where(SubscriptionConfigVersion.is_current.is_(True))
            .values(is_current=False)
        )
        session.add(SubscriptionConfigVersion(ordered_inst_ids=accepted, is_current=True))
        return SubscriptionUpdateResult(accepted=accepted, rejected=rejected)


async def list_live_selected_with_type() -> list[tuple[str, str]]:
    """已选且当前 live 的 (instId, instType) 列表——用于驱动持续采集的 desired 集合。"""

    full = await list_live_selected_full()
    return [(inst_id, inst_type) for inst_id, inst_type, _ in full]


async def list_live_selected_full() -> list[tuple[str, str, str | None]]:
    """已选且当前 live 的 (instId, instType, instFamily) 列表。

    instFamily 用于把某些 instType=SWAP 全局订阅的 WS 频道在应用层过滤/归属到
    已选产品；其余频道仍只需 instType。
    """

    selection = await get_current_selection()
    if not selection:
        return []
    async with session_scope() as session:
        result = await session.scalars(
            select(InstrumentCatalogVersion).where(
                InstrumentCatalogVersion.inst_id.in_(selection),
                InstrumentCatalogVersion.is_current.is_(True),
                InstrumentCatalogVersion.state == "live",
            )
        )
        rows = {row.inst_id: (row.inst_type, row.inst_family) for row in result.all()}
    return [
        (inst_id, rows[inst_id][0], rows[inst_id][1]) for inst_id in selection if inst_id in rows
    ]
