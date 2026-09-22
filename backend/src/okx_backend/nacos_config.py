"""从 Nacos 远程配置获取 MySQL / Redis 连接信息。

模式参照 /Users/lazycatnewton/development-repo/stock-view 的后端实现（Go）：
- Nacos 客户端自身的连接信息（服务地址、命名空间、账号密码）只来自环境变量，
  用于让本进程"找到并登录" Nacos；这些环境变量本身不是业务凭证。
- 业务凭证（MySQL / Redis 的账号密码等）保存在 Nacos 的远程配置项（YAML 内容）中，
  启动时拉取一次并用来覆盖 Settings 中对应字段；不在本仓库、不在 .env 中硬编码真实密码。
- 是否启用 Nacos 由启动参数 `ENV` 决定：`ENV=prod` 强制启用，`ENV=localhost` 强制禁用
  （完全跳过，直接从 `.env.localhost` 读取 MySQL/Redis，不需要真实 Nacos 服务）。

不确定/未验证事项：
- Nacos 侧 Data ID、Group、YAML 结构（database/redis 顶层键）需要与实际 Nacos 配置管理端
  的发布内容一致；本模块按 stock-view 的既有约定实现，具体键名如与本项目使用的 Nacos
  配置不一致，需要用户确认后调整 `NacosRemoteConfig` 的字段映射。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import yaml
from loguru import logger
from v2.nacos import ClientConfigBuilder, ConfigParam, NacosConfigService


@dataclass(frozen=True)
class NacosBootstrap:
    enabled: bool
    server_address: str
    namespace_id: str
    username: str | None
    password: str | None
    data_id: str
    group: str
    timeout_ms: int


def _get_env(key: str, default: str) -> str:
    value = os.environ.get(key, "").strip()
    return value or default


def load_nacos_bootstrap() -> NacosBootstrap:
    """Nacos 客户端自身的连接信息：只来自服务器环境变量，不来自 .env 文件业务配置。

    是否启用由 `ENV` 驱动而非 `NACOS_ENABLED` 开关：`ENV=prod` 强制启用（MySQL/Redis
    必须走 Nacos），`ENV=localhost` 强制禁用（完全跳过，直接用本地 `.env.localhost`）。
    `NACOS_ENABLED` 环境变量本身不再读取，避免 `ENV=prod` 却忘记同步设置
    `NACOS_ENABLED=true` 这种不一致状态。
    """

    from okx_backend.config import get_app_env

    return NacosBootstrap(
        enabled=get_app_env() == "prod",
        server_address=_get_env("NACOS_SERVER_ADDR", "localhost:8848"),
        namespace_id=_get_env("NACOS_NAMESPACE_ID", ""),
        username=os.environ.get("NACOS_USERNAME", "").strip() or None,
        password=os.environ.get("NACOS_PASSWORD") or None,
        data_id=_get_env("NACOS_DATA_ID", "okx.yaml"),
        group=_get_env("NACOS_GROUP", "DEFAULT_GROUP"),
        timeout_ms=int(_get_env("NACOS_TIMEOUT_MS", "5000")),
    )


@dataclass(frozen=True)
class RemoteStorageConfig:
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    redis_host: str
    redis_port: int
    redis_username: str | None
    redis_password: str | None


def _parse_remote_yaml(content: str) -> RemoteStorageConfig:
    parsed = yaml.safe_load(content) or {}
    database = parsed.get("database") or {}
    redis = parsed.get("redis") or {}

    missing = [
        key
        for key in ("host", "port", "user", "password", "name")
        if not str(database.get(key, "")).strip()
    ]
    if missing:
        raise ValueError(f"Nacos 配置缺少 database.{{{', '.join(missing)}}}")
    if not str(redis.get("host", "")).strip() or not str(redis.get("port", "")).strip():
        raise ValueError("Nacos 配置缺少 redis.host / redis.port")

    return RemoteStorageConfig(
        mysql_host=str(database["host"]),
        mysql_port=int(database["port"]),
        mysql_user=str(database["user"]),
        mysql_password=str(database["password"]),
        mysql_database=str(database["name"]),
        redis_host=str(redis["host"]),
        redis_port=int(redis["port"]),
        redis_username=str(redis["username"]) if redis.get("username") else None,
        redis_password=str(redis["password"]) if redis.get("password") else None,
    )


async def fetch_remote_storage_config(bootstrap: NacosBootstrap) -> RemoteStorageConfig:
    """连接 Nacos 并拉取一次远程配置，解析为 MySQL/Redis 连接信息。

    调用方负责决定拉取失败时的降级策略（本函数只抛出异常，不吞掉错误）。
    """

    client_config = (
        ClientConfigBuilder()
        .server_address(bootstrap.server_address)
        .namespace_id(bootstrap.namespace_id)
        .username(bootstrap.username or "")
        .password(bootstrap.password or "")
        .timeout_ms(bootstrap.timeout_ms)
        .build()
    )
    client = await NacosConfigService.create_config_service(client_config)
    try:
        content = await client.get_config(
            ConfigParam(data_id=bootstrap.data_id, group=bootstrap.group)
        )
    finally:
        await client.shutdown()

    if not content or not content.strip():
        raise ValueError(f"Nacos 配置 {bootstrap.data_id}@{bootstrap.group} 为空")

    logger.info(f"loaded remote storage config from Nacos: {bootstrap.data_id}@{bootstrap.group}")
    return _parse_remote_yaml(content)
