"""Tests for pantry opt-in shop gate (is_pantry + pantry_to_buy)."""

from meal_planner.ingredients import build_shopping_ingredients
from meal_planner.pantry import (
    collect_required_pantry,
    is_owned_pantry,
    pantry_uses_note,
)
from shared.models import Ingredient, Meal, MealSlot, MealsRequested, UserProfile


def _profile(**kwargs) -> UserProfile:
    return UserProfile(
        household_size=2,
        days=2,
        meals_requested=MealsRequested(dinner=2, lunch=0, breakfast=0, snacks=0),
        budget_nzd=100,
        **kwargs,
    )


def test_is_owned_pantry_respects_ticks():
    soy = Ingredient(name="soy sauce", quantity=1, unit="bottle", is_pantry=True)
    assert is_owned_pantry(soy, []) is True
    assert is_owned_pantry(soy, ["soy sauce"]) is False
    chicken = Ingredient(name="chicken thighs", quantity=800, unit="g", is_pantry=False)
    assert is_owned_pantry(chicken, []) is False


def test_collect_and_note_first_seen():
    m1 = Meal(
        name="Stir fry",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="",
        ingredients=[
            Ingredient(name="chicken", quantity=400, unit="g"),
            Ingredient(name="soy sauce", quantity=1, unit="tbsp", is_pantry=True),
            Ingredient(name="salt", quantity=1, unit="tsp", is_pantry=True),
        ],
        steps=[],
    )
    m2 = Meal(
        name="Noodles",
        slot=MealSlot.DINNER,
        day_label="Tuesday",
        description="",
        ingredients=[
            Ingredient(name="noodles", quantity=400, unit="g"),
            Ingredient(name="soy sauce", quantity=1, unit="tbsp", is_pantry=True),
        ],
        steps=[],
    )
    assert collect_required_pantry([m1, m2]) == ["soy sauce", "salt"]
    assert pantry_uses_note(m1) == "Uses pantry: soy sauce, salt"
    assert pantry_uses_note(m2) == "Uses pantry: soy sauce"


def test_flatten_excludes_owned_pantry_includes_ticked():
    meal = Meal(
        name="Stir fry",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="chicken dinner",
        ingredients=[
            Ingredient(name="chicken thighs", quantity=800, unit="g"),
            Ingredient(name="soy sauce", quantity=1, unit="bottle", is_pantry=True),
        ],
        steps=["Cook"],
    )
    names_default = {i.name for i in build_shopping_ingredients([meal], _profile())}
    assert "soy sauce" not in names_default
    assert "chicken thighs" in names_default
    names_buy = {
        i.name
        for i in build_shopping_ingredients([meal], _profile(), pantry_to_buy=["soy sauce"])
    }
    assert "soy sauce" in names_buy
