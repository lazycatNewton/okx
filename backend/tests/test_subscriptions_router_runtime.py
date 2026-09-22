from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from okx_backend.api import subscriptions_router
from okx_backend.auth.session import SessionData
from okx_backend.services import selection_data_runtime
from okx_backend.services.subscriptions import SubscriptionUpdateResult


@pytest.mark.asyncio
async def test_update_selection_applies_runtime_data_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_products = [("ETH-USDT-SWAP", "SWAP", "ETH-USDT")]
    collector = SimpleNamespace(apply_selected_products=lambda products: None)
    runtime = SimpleNamespace(apply_products=AsyncMock())

    monkeypatch.setattr(
        subscriptions_router,
        "set_selection",
        AsyncMock(
            return_value=SubscriptionUpdateResult(
                accepted=["ETH-USDT-SWAP"],
                rejected=[],
            )
        ),
    )
    monkeypatch.setattr(
        subscriptions_router,
        "list_live_selected_full",
        AsyncMock(return_value=live_products),
    )
    monkeypatch.setattr(subscriptions_router, "get_collector", lambda: collector)
    monkeypatch.setattr(
        selection_data_runtime,
        "get_selection_data_runtime",
        lambda: runtime,
    )

    response = await subscriptions_router.update_selection(
        subscriptions_router.UpdateSelectionRequest(instIds=["ETH-USDT-SWAP"]),
        SessionData(user_id=1, username="testuser", created_at=0),
    )

    assert response == {"accepted": ["ETH-USDT-SWAP"], "rejected": []}
    runtime.apply_products.assert_awaited_once_with(
        [("ETH-USDT-SWAP", "SWAP")],
        collector,
    )
