"""Tests for meal planner."""

import pytest

from meal_planner.ingredients import deduplicate_ingredients, filter_allergens
from meal_planner.planner import MealPlanner
from shared.models import Ingredient, MealsRequested, SimplicityLevel, UserProfile


def _profile(**kwargs) -> UserProfile:
    defaults = dict(
        household_size=2,
        meals_requested=MealsRequested(dinner=2, lunch=1),
        budget_nzd=100,
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def test_deduplicate_ingredients_merges_quantities():
    items = [
        Ingredient(name="onion", quantity=1, unit="each", for_meals=["Meal A"]),
        Ingredient(name="onion", quantity=2, unit="each", for_meals=["Meal B"]),
    ]
    merged = deduplicate_ingredients(items)
    assert len(merged) == 1
    assert merged[0].quantity == 3
    assert set(merged[0].for_meals) == {"Meal A", "Meal B"}


def test_filter_allergens_blocks_matching_ingredients():
    profile = _profile(allergies=["peanut"])
    items = [
        Ingredient(name="peanut butter", quantity=1, unit="jar"),
        Ingredient(name="rice", quantity=1, unit="bag"),
    ]
    safe = filter_allergens(items, profile)
    assert len(safe) == 1
    assert safe[0].name == "rice"


@pytest.mark.asyncio
async def test_template_planner_generates_meals():
    planner = MealPlanner(api_key=None)
    plan = await planner.generate(_profile(dinner=2, lunch=1))
    assert len(plan.meals) == 3
    assert len(plan.shared_ingredients) > 0


@pytest.mark.asyncio
async def test_swap_meal_changes_one_meal():
    planner = MealPlanner(api_key=None)
    profile = _profile(dinner=2)
    plan = await planner.generate(profile)
    original_name = plan.meals[0].name
    plan = planner.swap_meal(plan, 0, profile)
    assert plan.meals[0].name != original_name
