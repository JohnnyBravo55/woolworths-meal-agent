"""Woolworths NZ login — sign in via the user's default browser, import session cookies."""

from __future__ import annotations

import asyncio
import time

from woolies_cli.browser import AuthError
from woolies_cli.paths import cookies_file

from woolworths_adapter.browser_open import open_sign_in_in_browser
from woolworths_adapter.cookie_import import import_system_browser_cookies
from woolworths_adapter.session_paths import clear_woolworths_session_files


async def login_woolworths_interactive(
    *,
    timeout_seconds: float = 300,
    poll_interval_seconds: float = 3.0,
    open_browser: bool = True,
) -> None:
    """
    Open Woolworths in the user's default browser and wait until signed-in cookies appear.

    SmartCart never receives the password — only session cookies copied from Chrome,
    Edge, or Firefox are stored locally for API calls.
    """
    from woolworths_adapter.client import WoolworthsAdapter

    if open_browser:
        open_sign_in_in_browser()
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        imported = await asyncio.to_thread(import_system_browser_cookies)
        if imported:
            try:
                if await asyncio.wait_for(WoolworthsAdapter().is_live(), timeout=15.0):
                    return
            except (asyncio.TimeoutError, Exception):
                pass
        await asyncio.sleep(poll_interval_seconds)

    raise AuthError(
        "Sign-in timed out. Open https://account.woolworths.co.nz/ in Chrome, Edge, or Firefox, "
        "sign in, then click Connect again."
    )


def session_exists() -> bool:
    return cookies_file().exists()


def disconnect_woolworths_session() -> None:
    """Remove stored Woolworths cookies and any cached credentials."""
    clear_woolworths_session_files()


async def run_login_interactive_cli() -> None:
    """CLI entry — default browser sign-in."""
    await login_woolworths_interactive()
