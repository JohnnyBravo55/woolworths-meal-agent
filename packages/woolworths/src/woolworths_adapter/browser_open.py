"""Open Woolworths NZ in the user's default browser."""

from __future__ import annotations

import subprocess
import sys
import webbrowser

from woolworths_adapter.client import WOOLWORTHS_CART_URL

WOOLWORTHS_HOME_URL = "https://www.woolworths.co.nz"
# Shop homepage — user clicks Sign in (account.woolworths.co.nz alone may not activate trolley API).
WOOLWORTHS_SIGN_IN_URL = f"{WOOLWORTHS_HOME_URL}/"
WOOLWORTHS_ACCOUNT_URL = "https://account.woolworths.co.nz/"


def _open_url(url: str) -> None:
    """Open a URL in the user's default browser (best-effort on Windows services)."""
    opened = webbrowser.open(url, new=2)
    if opened:
        return
    if sys.platform == "win32":
        # webbrowser often fails from background API processes on Windows.
        subprocess.Popen(
            ["cmd", "/c", "start", "", url],
            shell=False,
            close_fds=True,
        )
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", url], close_fds=True)


def open_sign_in_in_browser() -> None:
    """Open Woolworths sign-in in the default browser (Chrome, Edge, Firefox, etc.)."""
    _open_url(WOOLWORTHS_SIGN_IN_URL)


def open_cart_in_browser(url: str = WOOLWORTHS_CART_URL) -> None:
    """
    Open Woolworths cart page in the default browser.

    Cart items are stored on your Woolworths account server-side, so if you are
    logged in to woolworths.co.nz in that browser you should see the same trolley.
    """
    _open_url(url)
