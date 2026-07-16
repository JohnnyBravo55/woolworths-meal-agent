"""Subscription / premium access helpers."""

from __future__ import annotations

import os

from meal_agent_api.auth import User


def premium_unlocked(user: User | None) -> bool:
    """True when premium chefs are selectable."""
    if os.getenv("MEAL_AGENT_DEV_PREMIUM", "").strip() in ("1", "true", "yes"):
        return True
    return bool(user and user.is_subscriber)
