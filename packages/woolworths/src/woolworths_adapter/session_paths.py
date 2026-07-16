"""Per-user Woolworths cookie isolation via XDG path overrides."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path

from woolies_cli.paths import cookies_file, storage_file

# Serialize env swaps — woolies-cli reads paths from os.environ at call time.
_env_lock = threading.Lock()

PROJECT_ROOT = Path(__file__).resolve().parents[4]
USER_WOOLIES_ROOT = PROJECT_ROOT / "data" / "woolworths_sessions"


def resolve_woolworths_user_id(session_user_id: str | None, auth_user_id: str | None) -> str | None:
    """Pick the cookie store for Woolworths — session owner first, then signed-in app user."""
    if session_user_id:
        return session_user_id
    if auth_user_id:
        return auth_user_id
    return None


def woolworths_session_dir(user_id: str | None) -> Path | None:
    if not user_id:
        return None
    return USER_WOOLIES_ROOT / user_id


def session_env_for_user(user_id: str | None, base: dict[str, str] | None = None) -> dict[str, str]:
    """Build env dict with XDG paths for an isolated Woolworths session."""
    env = dict(base or os.environ)
    root = woolworths_session_dir(user_id)
    if root is not None:
        env["XDG_STATE_HOME"] = str(root / "state")
        env["XDG_CONFIG_HOME"] = str(root / "config")
    return env


@contextmanager
def woolworths_session_context(user_id: str | None):
    """
    Temporarily point woolies-cli at this user's cookie store.

    When user_id is None, uses the default machine-wide ~/.local/state/woolies-nz-cli.
    """
    root = woolworths_session_dir(user_id)
    with _env_lock:
        prev_state = os.environ.get("XDG_STATE_HOME")
        prev_config = os.environ.get("XDG_CONFIG_HOME")
        if root is not None:
            (root / "state").mkdir(parents=True, exist_ok=True)
            (root / "config").mkdir(parents=True, exist_ok=True)
            os.environ["XDG_STATE_HOME"] = str(root / "state")
            os.environ["XDG_CONFIG_HOME"] = str(root / "config")
    try:
        yield
    finally:
        with _env_lock:
            if root is not None:
                if prev_state is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = prev_state
                if prev_config is None:
                    os.environ.pop("XDG_CONFIG_HOME", None)
                else:
                    os.environ["XDG_CONFIG_HOME"] = prev_config


def clear_woolworths_session_files() -> None:
    """Delete cookies and browser storage for the current XDG paths."""
    from woolies_cli.config import remove_credentials

    for path in (cookies_file(), storage_file()):
        if path.exists():
            path.unlink()
    remove_credentials()

