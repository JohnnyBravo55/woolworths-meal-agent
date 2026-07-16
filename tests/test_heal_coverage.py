"""Tests for post-resolve shop coverage heal protocol."""

import pytest

from meal_planner.shop_coverage import heal_resolved_coverage
from shared.models import (
    GroceryLineItem,
    Ingredient,
    LunchMode,
    Meal,
    MealSlot,
    MealsRequested,
    UserProfile,
)


def _profile(**kwargs) -> UserProfile:
    defaults = dict(
        household_size=2,
        meals_requested=MealsRequested(dinner=3, lunch=1, snacks=0),
        budget_nzd=250,
        allergies=["gluten"],
        mandatory_items=["gluten free bread", "milk"],
        pantry_items=["soy sauce", "olive oil", "salt", "pepper"],
        lunch_mode=LunchMode.ORIGINAL,
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _line(ingredient: str, *, sku: str = "1", meals: list[str] | None = None) -> GroceryLineItem:
    return GroceryLineItem(
        ingredient=ingredient,
        sku=sku,
        product_name=f"{ingredient} product",
        quantity=1,
        unit="Each",
        unit_price=5,
        line_total=5,
        for_meals=list(meals or []),
        in_stock=True,
    )


def test_heal_adds_missing_ingredients_as_manual():
    profile = _profile()
    dinner = Meal(
        name="Miso Salmon with Quinoa",
        slot=MealSlot.DINNER,
        day_label="Wednesday",
        description="Salmon with quinoa.",
        ingredients=[
            Ingredient(name="salmon fillets", quantity=400, unit="g"),
            Ingredient(name="quinoa", quantity=1, unit="bag"),
            Ingredient(name="miso paste", quantity=2, unit="tbsp"),
        ],
        steps=["Bake salmon."],
    )
    # Resolved list missing quinoa and miso
    items = [_line("salmon fillets", meals=[dinner.name])]
    healed, issues = heal_resolved_coverage([dinner], items, profile)
    names = {i.ingredient for i in healed}
    assert "quinoa" in names
    assert "miso paste" in names
    quinoa = next(i for i in healed if i.ingredient == "quinoa")
    assert quinoa.sku == "OFFLINE"
    assert dinner.name in quinoa.for_meals
    assert issues == []


def test_heal_links_cooked_salmon_lunch_to_dinner_salmon():
    profile = _profile()
    dinner = Meal(
        name="Miso Salmon Dinner",
        slot=MealSlot.DINNER,
        day_label="Wednesday",
        description="Fresh salmon.",
        ingredients=[Ingredient(name="salmon fillets", quantity=400, unit="g")],
        steps=["Bake."],
    )
    lunch = Meal(
        name="Miso Salmon Salad",
        slot=MealSlot.LUNCH,
        day_label="Wednesday",
        description="Salad with cooked salmon fillet.",
        ingredients=[
            Ingredient(name="cooked salmon fillet", quantity=200, unit="g"),
            Ingredient(name="mixed salad greens", quantity=1, unit="bag"),
        ],
        steps=["Assemble salad."],
    )
    items = [
        _line("salmon fillets", meals=[dinner.name]),
        _line("mixed salad greens", meals=[lunch.name]),
    ]
    healed, issues = heal_resolved_coverage([dinner, lunch], items, profile)
    salmon = next(i for i in healed if i.ingredient == "salmon fillets")
    assert lunch.name in salmon.for_meals
    assert not any(i.ingredient == "cooked salmon fillet" for i in healed)


def test_heal_does_not_add_pantry_items():
    profile = _profile()
    meal = Meal(
        name="Stir Fry",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="",
        ingredients=[
            Ingredient(name="chicken breast", quantity=400, unit="g"),
            Ingredient(name="soy sauce", quantity=1, unit="bottle"),
        ],
        steps=[],
    )
    items = [_line("chicken breast", meals=[meal.name])]
    healed, _ = heal_resolved_coverage([meal], items, profile)
    assert not any(i.ingredient == "soy sauce" for i in healed)


@pytest.mark.asyncio
async def test_resolve_all_heals_missing_after_offline_resolve():
    from woolworths_adapter.resolver import ProductResolver

    profile = _profile()
    dinner = Meal(
        name="Quinoa Bowl",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="",
        ingredients=[
            Ingredient(name="quinoa", quantity=1, unit="bag", for_meals=["Quinoa Bowl"]),
            Ingredient(name="chicken breast", quantity=400, unit="g", for_meals=["Quinoa Bowl"]),
        ],
        steps=[],
    )
    from shared.models import MealPlan

    plan = MealPlan(meals=[dinner], shared_ingredients=dinner.ingredients)
    resolver = ProductResolver(offline_mode=True)
    # Pass incomplete ingredient list — heal must restore quinoa from meal plan
    incomplete = [
        Ingredient(name="chicken breast", quantity=400, unit="g", for_meals=[dinner.name])
    ]
    resolved = await resolver.resolve_all(incomplete, profile, meal_plan=plan)
    names = {i.ingredient for i in resolved.items}
    assert "chicken breast" in names
    assert "quinoa" in names
    quinoa = next(i for i in resolved.items if i.ingredient == "quinoa")
    assert quinoa.sku == "OFFLINE"
    assert dinner.name in quinoa.for_meals
