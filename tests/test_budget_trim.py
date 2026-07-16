"""Tests for budget trim and cart guard."""

import pytest

from shared.models import (
    BudgetMode,
    ConversationState,
    GroceryLineItem,
    Ingredient,
    Meal,
    MealPlan,
    MealSlot,
    MealsRequested,
    ResolvedGroceryList,
    UserProfile,
)
from agent.budget import BudgetEngine
from agent.orchestrator import MealAgentOrchestrator


def _profile(budget: float = 100) -> UserProfile:
    return UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=3),
        budget_nzd=budget,
        budget_mode=BudgetMode.HARD,
    )


def test_trim_to_budget_drops_expensive_optional_items():
    engine = BudgetEngine()
    resolved = ResolvedGroceryList(
        items=[
            GroceryLineItem(
                ingredient="milk",
                sku="1",
                product_name="Milk",
                quantity=1,
                unit_price=5,
                line_total=5,
                is_mandatory=True,
            ),
            GroceryLineItem(
                ingredient="salmon",
                sku="2",
                product_name="Salmon",
                quantity=1,
                unit_price=80,
                line_total=80,
            ),
            GroceryLineItem(
                ingredient="rice",
                sku="3",
                product_name="Rice",
                quantity=1,
                unit_price=4,
                line_total=4,
            ),
        ],
        total=89,
        budget_nzd=50,
    )
    trimmed = engine.trim_to_budget(resolved, _profile(50))
    assert trimmed.total <= engine.effective_budget(_profile(50))
    assert any(i.ingredient == "milk" for i in trimmed.items)
    assert not any(i.ingredient == "salmon" for i in trimmed.items)


@pytest.mark.asyncio
async def test_reconcile_budget_reheals_trimmed_meal_coverage():
    """Hard trim must not leave dinners without required ingredients."""
    profile = _profile(20)
    dinner = Meal(
        name="Thai Green Chicken Curry",
        slot=MealSlot.DINNER,
        day_label="Wednesday",
        description="Curry",
        ingredients=[
            Ingredient(name="chicken thighs", quantity=800, unit="g"),
            Ingredient(name="green curry paste", quantity=2, unit="tbsp"),
            Ingredient(name="rice", quantity=2, unit="cup"),
        ],
        steps=["Cook."],
    )
    orch = MealAgentOrchestrator()
    orch.state = ConversationState(
        meal_plan=MealPlan(meals=[dinner], shared_ingredients=[]),
    )
    resolved = ResolvedGroceryList(
        items=[
            GroceryLineItem(
                ingredient="chicken thighs",
                sku="99",
                product_name="Expensive thighs",
                quantity=1,
                unit_price=50,
                line_total=50,
                for_meals=[dinner.name],
            ),
            GroceryLineItem(
                ingredient="green curry paste",
                sku="2",
                product_name="Paste",
                quantity=1,
                unit_price=5,
                line_total=5,
                for_meals=[dinner.name],
            ),
            GroceryLineItem(
                ingredient="rice",
                sku="3",
                product_name="Rice",
                quantity=1,
                unit_price=4,
                line_total=4,
                for_meals=[dinner.name],
            ),
        ],
        total=59,
        budget_nzd=20,
        within_budget=False,
    )
    out, _ = await orch.reconcile_budget(resolved, profile, auto_swap=False)
    names = {i.ingredient for i in out.items}
    assert "chicken thighs" in names
    assert "green curry paste" in names
    assert "rice" in names
