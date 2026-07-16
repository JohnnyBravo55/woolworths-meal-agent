"""Tests for budget engine."""

from shared.models import GroceryLineItem, ResolvedGroceryList, UserProfile, MealsRequested
from agent.budget import BudgetEngine


def _profile(budget: float = 100) -> UserProfile:
    return UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=3),
        budget_nzd=budget,
    )


def _resolved(total: float, budget: float = 100) -> ResolvedGroceryList:
    items = [
        GroceryLineItem(
            ingredient="milk",
            sku="111",
            product_name="Milk 2L",
            quantity=1,
            unit_price=4.0,
            line_total=4.0,
            is_mandatory=True,
        ),
        GroceryLineItem(
            ingredient="chicken",
            sku="222",
            product_name="Chicken 500g",
            quantity=1,
            unit_price=total - 4,
            line_total=total - 4,
        ),
    ]
    return ResolvedGroceryList(
        items=items,
        mandatory_subtotal=4.0,
        meal_subtotal=total - 4,
        total=total,
        budget_nzd=budget,
        within_budget=total <= budget,
    )


def test_budget_summarize():
    engine = BudgetEngine()
    summary = engine.summarize(_resolved(90))
    assert "Within budget" in summary


def test_budget_over_budget():
    engine = BudgetEngine()
    summary = engine.summarize(_resolved(120, budget=100))
    assert "Over budget" in summary


def test_effective_budget_includes_slack():
    engine = BudgetEngine()
    profile = _profile(100)
    assert engine.effective_budget(profile) == 95.0
