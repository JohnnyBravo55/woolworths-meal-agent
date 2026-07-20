"""Subscription / premium access helpers."""

from __future__ import annotations

import os

from meal_agent_api.auth import User


def premium_unlocked(user: User | None) -> bool:
    """True when premium chefs are selectable.

    Beta default: everyone is unlocked. Set MEAL_AGENT_PREMIUM_REQUIRED=1
    to gate on subscription (or MEAL_AGENT_DEV_PREMIUM=1 to force unlock).
    """
    if os.getenv("MEAL_AGENT_DEV_PREMIUM", "").strip() in ("1", "true", "yes"):
        return True
    if os.getenv("MEAL_AGENT_PREMIUM_REQUIRED", "").strip() in ("1", "true", "yes"):
        return bool(user and user.is_subscriber)
    return True
