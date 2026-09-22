"""应用配置。

配置来源：环境变量 / .env 文件。远程 MySQL 连接信息由用户通过环境变量提供，
本文件不写入任何真实凭证，也不提供默认密码。

启动参数 `ENV`（`localhost` / `prod`，未设置时默认为 `localhost`）决定配置装载方式：
- `ENV=localhost`（或未设置 `ENV`）：从 `.env.localhost` 文件 + OS 环境变量读取
  （OS 环境变量优先级更高）；Nacos 被完全跳过，MySQL/Redis 直接使用 `.env.localhost` 中的值。
- `ENV=prod`：不加载任何 dotenv 文件，全部配置只能来自真实 OS 环境变量；MySQL/Redis
  强制走 Nacos 远程配置（见 `nacos_config.py`），不再依赖 `NACOS_ENABLED` 开关。
`ENV` 取值非法（既不是 `localhost` 也不是 `prod`）时直接抛异常终止启动，不做静默降级——
生产环境必须显式传入 `ENV=prod`，本地开发可省略 `ENV` 或显式传 `ENV=localhost`。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["localhost", "prod"]
_VALID_APP_ENVS: tuple[AppEnv, ...] = ("localhost", "prod")
_DEFAULT_APP_ENV: AppEnv = "localhost"

# `.env.localhost` 必须用绝对路径锚定到 backend/ 包根目录（本文件位于
# backend/src/okx_backend/config.py，向上三级即 backend/），不能用相对路径。
# pydantic-settings 的相对 env_file 路径按进程当前工作目录解析：uvicorn/alembic
# 若不是从 backend/ 目录启动（例如从仓库根目录或用绝对路径调用），相对路径会
# 静默找不到文件、所有字段退回默认值（如 mysql_password 默认空字符串），不报错，
# 只在真正连接 MySQL 时才会看到 "Access denied ... (using password: NO)"。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_LOCALHOST_PATH = _BACKEND_ROOT / ".env.localhost"


def get_app_env() -> AppEnv:
    """读取启动参数 `ENV`；未设置时默认为 `localhost`，非法值直接报错。"""

    raw = os.environ.get("ENV", "").strip()
    if not raw:
        return _DEFAULT_APP_ENV
    if raw not in _VALID_APP_ENVS:
        raise RuntimeError(
            f"环境变量 ENV 取值非法（当前为 {raw!r}）；只能是 'localhost' 或 'prod'。"
        )
    return raw  # type: ignore[return-value]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_LOCALHOST_PATH),
        env_file_encoding="utf-8",
        env_prefix="OKX_APP_",
        extra="ignore",
    )

    # --- 数据库（MySQL 8.0+，远程实例，见 okx-requirements.md 已确定的系统组成）---
    mysql_host: str = Field(default="127.0.0.1")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="okx_app")
    mysql_password: str = Field(default="")
    mysql_database: str = Field(default="okx_app")

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    # --- Redis（仅缓存最新状态与会话，不作为永久数据来源）---
    redis_host: str = Field(default="127.0.0.1")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: str | None = Field(default=None)

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # --- OKX 全球站实盘（okx-requirements.md 第 1 节 / 第 3 节接口依据）---
    okx_rest_base: str = Field(default="https://www.okx.com")
    okx_ws_public: str = Field(default="wss://ws.okx.com:8443/ws/v5/public")
    okx_ws_business: str = Field(default="wss://ws.okx.com:8443/ws/v5/business")
    # M23 经济日历所需鉴权；未配置时应用按需求返回空数据集，不报错。
    okx_api_key: str | None = Field(default=None)
    okx_api_secret: str | None = Field(default=None)
    okx_api_passphrase: str | None = Field(default=None)

    # --- 数据保留 ---
    retention_days: int = Field(default=7)

    # --- 内部策略消费者接口（仅同一部署环境内网访问，本第一版不做额外鉴权中间件）---
    internal_bind_note: str = Field(
        default="内部 /internal/v1/* 假定仅监听内网接口；具体网络隔离属于暂缓的部署设计"
    )

    debug: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    app_env = get_app_env()
    if app_env == "prod":
        # prod 模式：不加载任何 dotenv 文件，全部配置必须来自真实 OS 环境变量。
        return Settings(_env_file=None)  # type: ignore[call-arg]
    # localhost 模式：从 .env.localhost 加载（model_config 中已配置该文件名）。
    return Settings()


def apply_remote_storage_config(
    settings: Settings,
    *,
    mysql_host: str,
    mysql_port: int,
    mysql_user: str,
    mysql_password: str,
    mysql_database: str,
    redis_host: str,
    redis_port: int,
    redis_password: str | None,
) -> None:
    """用 Nacos 远程配置覆盖已缓存的 Settings 实例（原地修改）。

    `get_settings()` 使用 `lru_cache` 缓存单例，多个模块在导入期已经持有该实例的引用
    （例如各 router 模块顶层的 `_settings = get_settings()`）；原地修改字段可以让这些
    早于 Nacos 拉取完成就已导入的引用同样生效，而不需要让调用方重新获取一次 Settings。
    """

    settings.mysql_host = mysql_host
    settings.mysql_port = mysql_port
    settings.mysql_user = mysql_user
    settings.mysql_password = mysql_password
    settings.mysql_database = mysql_database
    settings.redis_host = redis_host
    settings.redis_port = redis_port
    settings.redis_password = redis_password
