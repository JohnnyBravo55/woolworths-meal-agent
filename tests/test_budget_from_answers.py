"""Blank weekly budget stays optional and becomes a soft default server-side."""

from agent.conversation import (
    ConversationManager,
    _budget_mode_from_answers,
    _budget_nzd_from_answers,
)
from shared.models import BudgetMode


def test_blank_budget_uses_soft_default():
    assert _budget_nzd_from_answers({"budget_nzd": 0}) == 200.0
    assert _budget_nzd_from_answers({"budget_nzd": ""}) == 200.0
    assert _budget_nzd_from_answers({}) == 200.0
    assert _budget_mode_from_answers({"budget_nzd": 0}) == BudgetMode.SOFT


def test_explicit_budget_is_hard():
    assert _budget_nzd_from_answers({"budget_nzd": 180}) == 180.0
    assert _budget_mode_from_answers({"budget_nzd": 180}) == BudgetMode.HARD


def test_profile_from_blank_budget():
    profile = ConversationManager().create_profile_from_answers(
        {
            "household_size": 2,
            "days": 7,
            "dinner_count": 3,
            "lunch_count": 0,
            "snack_count": 0,
            "allergies": "",
            "mandatory_items": "",
            "budget_nzd": 0,
        }
    )
    assert profile.budget_nzd == 200.0
    assert profile.budget_mode == BudgetMode.SOFT
    assert profile.allergies == []
    assert profile.mandatory_items == []
