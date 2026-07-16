"""Login works under Windows SelectorEventLoop (uvicorn default)."""

import asyncio
import sys

import pytest

from woolworths_adapter.login_subprocess import login_via_subprocess


@pytest.mark.asyncio
async def test_login_subprocess_no_notimplemented_on_selector_loop(monkeypatch):
    """Regression: login must not use asyncio.create_subprocess_exec on Windows."""
    if sys.platform != "win32":
        pytest.skip("Windows-only regression")

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def fake_is_live(self):
        return True

    monkeypatch.setattr(
        "woolworths_adapter.client.WoolworthsAdapter.is_live",
        fake_is_live,
    )

    async def fake_login(**_kwargs):
        return None

    monkeypatch.setattr(
        "woolworths_adapter.login.login_woolworths_interactive",
        fake_login,
    )

    await login_via_subprocess(user_id=None, timeout_seconds=5)
