"""Alembic 迁移环境。

使用同步 PyMySQL 驱动执行迁移（Alembic 对异步引擎的支持较繁琐，迁移操作本身是一次性的，
不需要走应用的异步连接池）；连接串复用 okx_backend.config.Settings。启动时必须设置
环境变量 `ENV`（`localhost` / `prod`，见 okx_backend.config.get_app_env）；`ENV=prod`
时先同步拉取一次 Nacos 远程配置覆盖 MySQL 连接信息，逻辑与 `okx_backend.main` 的应用
启动路径一致；`ENV=localhost` 时从 `.env.localhost` / OS 环境变量读取，不在本文件
写入任何凭证。
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from okx_backend.config import apply_remote_storage_config, get_settings
from okx_backend.db import models  # noqa: F401 - 确保所有模型注册到 Base.metadata
from okx_backend.db.base import Base
from okx_backend.nacos_config import fetch_remote_storage_config, load_nacos_bootstrap

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _apply_nacos_config_if_enabled_sync() -> None:
    bootstrap = load_nacos_bootstrap()
    if not bootstrap.enabled:
        return
    remote = asyncio.run(fetch_remote_storage_config(bootstrap))
    apply_remote_storage_config(
        get_settings(),
        mysql_host=remote.mysql_host,
        mysql_port=remote.mysql_port,
        mysql_user=remote.mysql_user,
        mysql_password=remote.mysql_password,
        mysql_database=remote.mysql_database,
        redis_host=remote.redis_host,
        redis_port=remote.redis_port,
        redis_username=remote.redis_username,
        redis_password=remote.redis_password,
    )


_apply_nacos_config_if_enabled_sync()


def _sync_dsn() -> str:
    settings = get_settings()
    return (
        f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}?charset=utf8mb4"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _sync_dsn()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
