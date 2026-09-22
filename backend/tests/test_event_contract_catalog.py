"""M22 事件合约辅助市场服务单元测试（fake fetch，不依赖真实网络/数据库）。"""

from __future__ import annotations

import pytest

from okx_backend.services.event_contract_catalog import (
    _payload_hash,
    _to_optional_int,
)


def test_to_optional_int_handles_empty_string_and_none() -> None:
    assert _to_optional_int(None) is None
    assert _to_optional_int("") is None
    assert _to_optional_int("1769697132335") == 1769697132335


def test_payload_hash_is_stable_for_same_content_different_key_order() -> None:
    a = {"instId": "X", "state": "live"}
    b = {"state": "live", "instId": "X"}
    assert _payload_hash(a) == _payload_hash(b)


def test_payload_hash_differs_for_different_content() -> None:
    a = {"instId": "X", "state": "live"}
    b = {"instId": "X", "state": "expired"}
    assert _payload_hash(a) != _payload_hash(b)


@pytest.mark.asyncio
async def test_apply_ws_update_records_revision_even_when_market_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WS 只推送状态变更，不保证本地已有该市场记录（如服务重启窗口内新上线的市场）；
    此时不应静默丢弃推送——至少要记录一条修订事件，目录会在下一次每小时校正时自愈。
    """

    import okx_backend.services.event_contract_catalog as module

    calls: list[tuple[str, dict]] = []

    class _FakeResult:
        def __init__(self, value):
            self._value = value

        async def scalar(self, *_a, **_kw):
            return self._value

        async def execute(self, stmt):
            calls.append(("execute", {}))

    class _FakeSessionScope:
        async def __aenter__(self):
            return _FakeResult(None)

        async def __aexit__(self, *exc):
            return None

    monkeypatch.setattr(module, "session_scope", lambda: _FakeSessionScope())

    row = {
        "instId": "BTC-ABOVE-DAILY-260224-1600-65000",
        "seriesId": "BTC-ABOVE-DAILY",
        "eventId": "BTC-ABOVE-DAILY-260224-1600",
        "state": "live",
        "floorStrike": "120000",
    }
    await module.apply_event_contract_ws_update(row)

    # 至少发起了一次 execute（修订事件插入）；未知市场不应抛异常中断整条推送处理。
    assert len(calls) >= 1
