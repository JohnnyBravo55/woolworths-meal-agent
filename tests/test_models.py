"""Tests for shared models."""

from shared.models import (
    BudgetMode,
    Ingredient,
    Meal,
    MealPlan,
    MealSlot,
    MealsRequested,
    UserProfile,
)


def test_user_profile_normalizes_allergies():
    profile = UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=5),
        allergies=[" Peanuts ", "GLUTEN"],
        budget_nzd=100,
    )
    assert profile.allergies == ["peanuts", "gluten"]


def test_legacy_household_size_becomes_all_adults():
    profile = UserProfile(
        household_size=3,
        meals_requested=MealsRequested(dinner=5),
        budget_nzd=100,
    )
    assert profile.adults == 3
    assert profile.children_under_13 == 0
    assert profile.adult_equivalent_servings == 3.0


def test_mixed_ages_compute_servings_and_headcount():
    profile = UserProfile(
        adults=2,
        children_under_13=2,
        children_age_bands={"1-3": 0, "4-6": 1, "7-9": 1, "10-12": 0},
        meals_requested=MealsRequested(dinner=5),
        budget_nzd=100,
    )
    assert profile.household_size == 4
    assert profile.adult_equivalent_servings == 3.5


def test_meals_requested_total():
    req = MealsRequested(breakfast=2, lunch=3, dinner=5, snacks=1)
    assert req.total_meals() == 11


def test_meal_plan_structure():
    meal = Meal(
        name="Test Meal",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="A test",
        ingredients=[Ingredient(name="chicken", quantity=500, unit="g")],
        steps=["Cook it"],
    )
    plan = MealPlan(meals=[meal], shared_ingredients=[Ingredient(name="chicken", quantity=500, unit="g")])
    assert len(plan.meals) == 1
    assert plan.shared_ingredients[0].name == "chicken"
