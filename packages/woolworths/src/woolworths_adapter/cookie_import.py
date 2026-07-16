"""Import Woolworths session cookies from the user's default system browser."""

from __future__ import annotations

import json
from http.cookiejar import Cookie
from typing import Callable

from woolies_cli.paths import cookies_file, state_dir

_AUTH_COOKIE_NAMES = frozenset(
    {
        "AUTH_SESSION_ID",
        "AUTH_SESSION_ID_LEGACY",
        "XSRF-TOKEN",
        "ASP.NET_SessionId",
    }
)


def _cookie_to_json(cookie: Cookie) -> dict:
    return {
        "name": cookie.name,
        "value": cookie.value,
        "domain": cookie.domain,
        "path": cookie.path or "/",
        "expires": float(cookie.expires) if cookie.expires else -1,
        "httpOnly": False,
        "secure": bool(cookie.secure),
        "sameSite": "Lax",
    }


def _collect_woolworths_cookies(loader: Callable) -> list[dict]:
    jar = loader(domain_name="woolworths.co.nz")
    cookies: list[dict] = []
    for cookie in jar:
        if "woolworths" not in (cookie.domain or ""):
            continue
        cookies.append(_cookie_to_json(cookie))
    return cookies


def _score_cookie_jar(cookies: list[dict]) -> int:
  score = len(cookies)
  for cookie in cookies:
      if cookie.get("name") in _AUTH_COOKIE_NAMES:
          score += 10
  return score


def import_system_browser_cookies() -> bool:
    """
    Read woolworths.co.nz cookies from Chrome, Edge, or Firefox and save for woolies-cli.

    Picks the browser jar with the strongest Woolworths auth signals.

    Returns True when at least one cookie was written.
    """
    import browser_cookie3

    loaders: list[tuple[str, Callable]] = [
        ("chrome", browser_cookie3.chrome),
        ("chromium", browser_cookie3.chromium),
        ("edge", browser_cookie3.edge),
        ("firefox", browser_cookie3.firefox),
    ]

    best: list[dict] = []
    best_score = 0
    for _name, loader in loaders:
        try:
            cookies = _collect_woolworths_cookies(loader)
        except Exception:
            continue
        if not cookies:
            continue
        score = _score_cookie_jar(cookies)
        if score > best_score:
            best = cookies
            best_score = score

    if not best:
        return False

    state_dir().mkdir(parents=True, exist_ok=True)
    cookies_file().write_text(json.dumps(best, indent=2), encoding="utf-8")
    return True
