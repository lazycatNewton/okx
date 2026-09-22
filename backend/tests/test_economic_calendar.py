"""M23 经济日历服务单元测试（不需要真实网络/凭证/数据库）。"""

from __future__ import annotations

import pytest

from okx_backend.okx_client.rest import OkxRestError
from okx_backend.services.economic_calendar import (
    _to_optional_int,
    credentials_configured,
    refresh_economic_calendar,
    start_economic_calendar_ws,
)


def test_credentials_configured_false_when_any_field_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import okx_backend.config as config_module

    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "okx_api_key", None)
    monkeypatch.setattr(settings, "okx_api_secret", "secret")
    monkeypatch.setattr(settings, "okx_api_passphrase", "pass")
    assert credentials_configured() is False


def test_credentials_configured_true_when_all_fields_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import okx_backend.config as config_module

    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "okx_api_key", "key")
    monkeypatch.setattr(settings, "okx_api_secret", "secret")
    monkeypatch.setattr(settings, "okx_api_passphrase", "pass")
    assert credentials_configured() is True


@pytest.mark.asyncio
async def test_refresh_returns_zero_without_making_any_request_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配置凭证时必须直接返回 0，不发起任何 REST 请求（需求文档：未配置凭证时返回空）。"""

    import okx_backend.config as config_module
    import okx_backend.services.economic_calendar as module

    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "okx_api_key", None)
    monkeypatch.setattr(settings, "okx_api_secret", None)
    monkeypatch.setattr(settings, "okx_api_passphrase", None)

    called = False

    class _ExplodingClient:
        async def __aenter__(self):
            nonlocal called
            called = True
            raise AssertionError("should not attempt to open a REST client when unconfigured")

        async def __aexit__(self, *exc):
            return None

    monkeypatch.setattr(module, "OkxRestClient", _ExplodingClient)

    result = await refresh_economic_calendar()
    assert result == 0
    assert called is False


@pytest.mark.asyncio
async def test_refresh_returns_zero_and_swallows_auth_or_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """鉴权失败/网络故障/非 VIP1 时统一返回空，不暴露错误详情、不向上抛异常。"""

    import okx_backend.config as config_module
    import okx_backend.services.economic_calendar as module

    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "okx_api_key", "key")
    monkeypatch.setattr(settings, "okx_api_secret", "secret")
    monkeypatch.setattr(settings, "okx_api_passphrase", "pass")

    class _FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get_economic_calendar(self, **kwargs):
            raise OkxRestError("50110", "Invalid IP or account not VIP1")

    monkeypatch.setattr(module, "OkxRestClient", _FailingClient)

    result = await refresh_economic_calendar()
    assert result == 0


def test_start_ws_returns_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    import okx_backend.config as config_module

    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "okx_api_key", None)
    monkeypatch.setattr(settings, "okx_api_secret", None)
    monkeypatch.setattr(settings, "okx_api_passphrase", None)
    assert start_economic_calendar_ws() is None


def test_start_ws_returns_client_with_login_provider_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import okx_backend.config as config_module

    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "okx_api_key", "key")
    monkeypatch.setattr(settings, "okx_api_secret", "secret")
    monkeypatch.setattr(settings, "okx_api_passphrase", "pass")
    client = start_economic_calendar_ws()
    assert client is not None
    assert client._login_args_provider is not None  # noqa: SLF001 - 白盒测试内部状态


def test_to_optional_int_handles_empty_and_none() -> None:
    assert _to_optional_int(None) is None
    assert _to_optional_int("") is None
    assert _to_optional_int("1700121600000") == 1700121600000
