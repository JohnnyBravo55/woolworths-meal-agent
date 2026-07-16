"""Tests for review gate."""

from agent.review import ReviewGate
from shared.models import GroceryLineItem, Meal, MealPlan, MealSlot, ResolvedGroceryList, UserProfile, MealsRequested


def test_review_gate_blocks_cart_without_approval():
    assert ReviewGate.can_add_to_cart(False, False) is False
    assert ReviewGate.can_add_to_cart(True, False) is False
    assert ReviewGate.can_add_to_cart(True, True) is True


def test_cart_disclaimer_mentions_no_checkout():
    assert "NEVER" in ReviewGate.cart_disclaimer()


def test_format_allergy_confirmation():
    profile = UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=1),
        allergies=["peanut"],
        budget_nzd=50,
    )
    msg = ReviewGate.format_allergy_confirmation(profile)
    assert "peanut" in msg


def test_format_meal_plan_summary():
    plan = MealPlan(
        meals=[
            Meal(
                name="Tacos",
                slot=MealSlot.DINNER,
                day_label="Monday",
                description="Quick tacos",
            )
        ]
    )
    summary = ReviewGate.format_meal_plan_summary(plan)
    assert "Tacos" in summary
    assert "Monday" in summary


def test_format_product_list():
    resolved = ResolvedGroceryList(
        items=[
            GroceryLineItem(
                ingredient="milk",
                sku="123",
                product_name="Milk 2L",
                quantity=1,
                unit_price=4.0,
                line_total=4.0,
                is_mandatory=True,
            )
        ],
        total=4.0,
        budget_nzd=100,
    )
    text = ReviewGate.format_product_list(resolved)
    assert "MANDATORY" in text
    assert "123" in text


def test_format_dinner_recipes_only():
    plan = MealPlan(
        meals=[
            Meal(
                name="Tacos",
                slot=MealSlot.DINNER,
                day_label="Monday",
                description="Quick tacos",
                steps=["Cook beef", "Serve"],
                ingredients=[],
            ),
            Meal(
                name="Wrap",
                slot=MealSlot.LUNCH,
                day_label="Tuesday",
                description="Lunch wrap",
                steps=["Assemble"],
                ingredients=[],
            ),
        ]
    )
    text = ReviewGate.format_dinner_recipes(plan)
    assert "Tacos" in text
    assert "Cook beef" in text
    assert "Wrap" not in text
