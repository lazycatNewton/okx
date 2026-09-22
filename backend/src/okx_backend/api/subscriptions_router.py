"""PUT /api/subscriptions/products — 更新全局产品选择（单例配置，无登录）。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from okx_backend.collector.market_collector import get_collector
from okx_backend.services import selection_data_runtime
from okx_backend.services.subscriptions import list_live_selected_full, set_selection

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class UpdateSelectionRequest(BaseModel):
    instIds: list[str]


@router.put("/products")
async def update_selection(payload: UpdateSelectionRequest) -> dict:
    result = await set_selection(payload.instIds)
    # 已选且 live 的产品持续采集；此处按最新选择重算 desired 订阅集合（不依赖任何浏览器 Tab 状态）。
    live_products = await list_live_selected_full()
    collector = get_collector()
    collector.apply_selected_products(live_products)
    # 产品运行期新增时，立即启动对应 K 线/M25 历史回填与 M25 周期轮询；
    # 不能只更新实时 WS 订阅，否则新增产品只能从选择后的时刻开始积累数据。
    await selection_data_runtime.get_selection_data_runtime().apply_products(
        [(inst_id, inst_type) for inst_id, inst_type, _ in live_products],
        collector,
    )
    return {"accepted": result.accepted, "rejected": result.rejected}
