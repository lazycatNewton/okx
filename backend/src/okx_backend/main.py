"""FastAPI 应用入口。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from okx_backend.api.aux_router import router as aux_router
from okx_backend.api.bootstrap_router import router as bootstrap_router
from okx_backend.api.m25_router import router as m25_router
from okx_backend.api.market_router import router as market_router
from okx_backend.api.products_router import router as products_router
from okx_backend.api.subscriptions_router import router as subscriptions_router
from okx_backend.api.ws_app_router import router as ws_app_router
from okx_backend.cache import close_redis
from okx_backend.collector.market_collector import get_collector
from okx_backend.config import apply_remote_storage_config, get_settings
from okx_backend.db.base import dispose_engine
from okx_backend.nacos_config import fetch_remote_storage_config, load_nacos_bootstrap
from okx_backend.services.catalog import refresh_catalog
from okx_backend.services.economic_calendar import (
    refresh_economic_calendar,
    run_economic_calendar_resync_forever,
    start_economic_calendar_ws,
)
from okx_backend.services.event_contract_catalog import (
    refresh_event_contract_catalog,
    run_event_contract_hourly_resync,
    start_event_contract_ws,
)
from okx_backend.services.retention import run_retention_cleanup_forever
from okx_backend.services.selection_data_runtime import get_selection_data_runtime
from okx_backend.services.subscriptions import list_live_selected_full


async def _apply_nacos_config_if_enabled() -> None:
    """若启用 Nacos，则用远程配置覆盖 MySQL/Redis 连接信息；必须在任何 DB/Redis 连接
    建立之前调用，否则已缓存的连接池会继续使用覆盖前的旧凭证。"""

    bootstrap = load_nacos_bootstrap()
    if not bootstrap.enabled:
        return
    remote = await fetch_remote_storage_config(bootstrap)
    apply_remote_storage_config(
        get_settings(),
        mysql_host=remote.mysql_host,
        mysql_port=remote.mysql_port,
        mysql_user=remote.mysql_user,
        mysql_password=remote.mysql_password,
        mysql_database=remote.mysql_database,
        redis_host=remote.redis_host,
        redis_port=remote.redis_port,
        redis_password=remote.redis_password,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 启动第一步：若启用 Nacos，先用远程配置覆盖 MySQL/Redis 连接信息，
    # 再进行任何数据库/缓存访问；Nacos 拉取失败时直接中止启动，不静默回退到占位配置，
    # 避免用错误或缺失的凭证误连到本地默认值。
    await _apply_nacos_config_if_enabled()

    # 刷新产品目录，再按已保存的订阅配置恢复持续采集（不等待浏览器连接）。
    try:
        appended = await refresh_catalog()
        logger.info(f"instrument catalog refreshed, {appended} versions appended")
    except Exception as exc:  # noqa: BLE001 - 启动期目录刷新失败不应阻塞服务本身
        logger.error(f"instrument catalog refresh failed at startup: {exc!r}")

    # M22 需求文档：首次启动混合回填顺序——先刷新 M22 全量系列/事件/市场目录（REST 是
    # 初始状态的唯一来源，WS 不推送快照），随后才建立 WS 订阅；因此这里必须同步等待，
    # 不能像 K 线/M25 历史那样丢给后台任务（否则 WS 更新可能作用在尚不存在的本地记录上）。
    try:
        counts = await refresh_event_contract_catalog()
        logger.info(f"event-contract catalog initialized: {counts}")
    except Exception as exc:  # noqa: BLE001 - 启动期目录刷新失败不应阻塞服务本身
        logger.error(f"event-contract catalog refresh failed at startup: {exc!r}")

    # M23：未配置凭证时 refresh 立即返回 0，不发起任何请求；已配置则尽力刷新一次，
    # 失败（鉴权/网络/非 VIP1）统一吞掉不影响启动。
    try:
        await refresh_economic_calendar()
    except Exception as exc:  # noqa: BLE001 - 与 refresh_economic_calendar 内部策略一致
        logger.error(f"economic-calendar refresh failed at startup: {exc!r}")

    collector = get_collector()
    collector.start()
    live_products_full = await list_live_selected_full()
    collector.apply_selected_products(live_products_full)
    restored_products = [(inst_id, inst_type) for inst_id, inst_type, _ in live_products_full]

    selection_data_runtime = get_selection_data_runtime()
    await selection_data_runtime.apply_products(restored_products, collector)
    retention_task = asyncio.create_task(run_retention_cleanup_forever())

    event_contract_ws = start_event_contract_ws()
    event_contract_ws.start()
    event_contract_resync_task = asyncio.create_task(run_event_contract_hourly_resync())

    # M23 WS 是可选的：仅在服务端配置了 OKX API 凭证时才建立连接；未配置时
    # `start_economic_calendar_ws()` 返回 None，对应资源保持为 None，关闭时按需跳过。
    economic_calendar_ws = start_economic_calendar_ws()
    if economic_calendar_ws is not None:
        economic_calendar_ws.start()
    economic_calendar_resync_task = asyncio.create_task(run_economic_calendar_resync_forever())

    try:
        yield
    finally:
        retention_task.cancel()
        event_contract_resync_task.cancel()
        economic_calendar_resync_task.cancel()
        await asyncio.gather(
            retention_task,
            event_contract_resync_task, economic_calendar_resync_task,
            return_exceptions=True,
        )
        await selection_data_runtime.stop()
        await event_contract_ws.stop()
        if economic_calendar_ws is not None:
            await economic_calendar_ws.stop()

    await collector.stop()
    await dispose_engine()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(title="OKX 行情连接服务", lifespan=lifespan)
    app.include_router(bootstrap_router)
    app.include_router(products_router)
    app.include_router(subscriptions_router)
    app.include_router(market_router)
    app.include_router(m25_router)
    app.include_router(aux_router)
    app.include_router(ws_app_router)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    return app


app = create_app()
