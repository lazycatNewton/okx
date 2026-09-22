"""Nacos 远程配置解析/校验的单元测试（不需要真实 Nacos 服务）。"""

from __future__ import annotations

import pytest

from okx_backend.nacos_config import _parse_remote_yaml, load_nacos_bootstrap


def test_load_nacos_bootstrap_disabled_when_env_is_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "localhost")
    bootstrap = load_nacos_bootstrap()
    assert bootstrap.enabled is False


def test_load_nacos_bootstrap_enabled_when_env_is_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("NACOS_SERVER_ADDR", "nacos.internal:8848")
    monkeypatch.setenv("NACOS_TIMEOUT_MS", "3000")
    bootstrap = load_nacos_bootstrap()
    assert bootstrap.enabled is True
    assert bootstrap.server_address == "nacos.internal:8848"
    assert bootstrap.timeout_ms == 3000


def test_parse_remote_yaml_success() -> None:
    content = """
database:
  host: mysql-host
  port: 3306
  user: okx_app
  password: secret
  name: okx_app
redis:
  host: redis-host
  port: 6379
  username: default
  password: redis-secret
"""
    cfg = _parse_remote_yaml(content)
    assert cfg.mysql_host == "mysql-host"
    assert cfg.mysql_port == 3306
    assert cfg.mysql_password == "secret"
    assert cfg.redis_host == "redis-host"
    assert cfg.redis_password == "redis-secret"


def test_parse_remote_yaml_missing_database_field_raises() -> None:
    content = "database:\n  host: mysql-host\n"
    with pytest.raises(ValueError, match="database"):
        _parse_remote_yaml(content)


def test_parse_remote_yaml_missing_redis_raises() -> None:
    content = """
database:
  host: mysql-host
  port: 3306
  user: okx_app
  password: secret
  name: okx_app
"""
    with pytest.raises(ValueError, match="redis"):
        _parse_remote_yaml(content)


def test_parse_remote_yaml_redis_credentials_optional() -> None:
    content = """
database:
  host: mysql-host
  port: 3306
  user: okx_app
  password: secret
  name: okx_app
redis:
  host: redis-host
  port: 6379
"""
    cfg = _parse_remote_yaml(content)
    assert cfg.redis_username is None
    assert cfg.redis_password is None
