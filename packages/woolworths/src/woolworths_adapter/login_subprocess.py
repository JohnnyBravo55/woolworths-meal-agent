"""Woolworths login — async entry used by the API."""

from __future__ import annotations

import asyncio

from woolies_cli.browser import AuthError

from woolworths_adapter.session_paths import woolworths_session_context


async def login_via_subprocess(
    *,
    user_id: str | None = None,
    timeout_seconds: float = 300,
    open_browser: bool = True,
) -> None:
    """
    Connect Woolworths using the system default browser (no Camoufox window).

    Opens woolworths.co.nz in Chrome/Edge/Firefox and imports session cookies.
    """
    from woolworths_adapter.client import WoolworthsAdapter
    from woolworths_adapter.login import login_woolworths_interactive

    with woolworths_session_context(user_id):
        await login_woolworths_interactive(
            timeout_seconds=timeout_seconds,
            open_browser=open_browser,
        )

    with woolworths_session_context(user_id):
        try:
            live = await asyncio.wait_for(WoolworthsAdapter().is_live(), timeout=15.0)
        except (asyncio.TimeoutError, Exception):
            live = False
        if not live:
            raise AuthError(
                "Sign-in finished but Woolworths session check failed. "
                "Make sure you are logged in on woolworths.co.nz in Chrome, Edge, or Firefox."
            )
