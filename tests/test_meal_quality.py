"""Tests for budget feasibility and meal quality."""

from meal_planner.budget_feasibility import check_budget_feasibility, estimate_plan_cost
from meal_planner.ingredients import build_shopping_ingredients
from meal_planner.meal_quality import enforce_culinary_coherence, ensure_meal_balance
from meal_planner.planner import MealPlanner
from shared.models import Ingredient, LunchMode, Meal, MealSlot, MealsRequested, UserProfile
import pytest


def _profile(**kwargs) -> UserProfile:
    defaults = dict(
        household_size=2,
        meals_requested=MealsRequested(dinner=6, lunch=6, snacks=5),
        budget_nzd=250,
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def test_budget_feasibility_warns_when_too_many_meals():
    result = check_budget_feasibility(_profile(budget_nzd=100))
    assert result.feasible is False
    assert result.suggested_meals is not None
    assert "budget" in result.message.lower()


def test_budget_feasible_for_small_plan():
    result = check_budget_feasibility(
        _profile(
            meals_requested=MealsRequested(dinner=3, lunch=2, snacks=1),
            budget_nzd=250,
        )
    )
    assert result.feasible is True


def test_practical_lunch_costs_less():
    original = estimate_plan_cost(_profile(lunch_mode=LunchMode.ORIGINAL, meals_requested=MealsRequested(lunch=5)))
    practical = estimate_plan_cost(_profile(lunch_mode=LunchMode.PRACTICAL, meals_requested=MealsRequested(lunch=5)))
    assert practical < original


def test_quinoa_removed_from_soup():
    meal = Meal(
        name="Chicken Soup",
        slot=MealSlot.DINNER,
        day_label="Tuesday",
        description="Soup",
        ingredients=[Ingredient(name="quinoa", quantity=1, unit="bag")],
        steps=["Simmer chicken soup with rice."],
    )
    out = enforce_culinary_coherence([meal])
    assert out[0].ingredients[0].name == "rice"


def test_prune_orphan_ingredients():
    meals = [
        Meal(
            name="Simple Pasta",
            slot=MealSlot.DINNER,
            day_label="Monday",
            description="",
            ingredients=[Ingredient(name="pasta", quantity=1, unit="pack")],
            steps=[],
        )
    ]
    items = build_shopping_ingredients(meals, _profile())
    names = {i.name for i in items}
    assert "pasta" in names
    assert "salsa" not in names
    assert "cheese" not in names


@pytest.mark.asyncio
async def test_snack_variety_in_templates():
    planner = MealPlanner(api_key=None)
    plan = await planner.generate(_profile(meals_requested=MealsRequested(dinner=2, snacks=3)))
    snacks = [m for m in plan.meals if m.slot == MealSlot.SNACK]
    names = {s.name for s in snacks}
    assert len(names) >= 2


def test_leftover_lunch_excludes_protein_from_shop_list():
    from meal_planner.meal_quality import is_leftover_meal

    dinner = Meal(
        name="Salmon Tray Bake",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="",
        ingredients=[Ingredient(name="salmon fillets", quantity=4, unit="each")],
        steps=[],
    )
    lunch = Meal(
        name="Leftover salmon wrap",
        slot=MealSlot.LUNCH,
        day_label="Tuesday",
        description="Use leftover salmon from yesterday",
        ingredients=[
            Ingredient(name="salmon fillets", quantity=2, unit="each"),
            Ingredient(name="tortilla wraps", quantity=1, unit="pack"),
        ],
        steps=["Reheat salmon and wrap."],
    )
    assert is_leftover_meal(lunch)
    items = build_shopping_ingredients([dinner, lunch], _profile(lunch_mode=LunchMode.PRACTICAL))
    names = {i.name for i in items}
    assert "salmon fillets" in names
    assert "tortilla wraps" in names


def test_preheat_dinner_is_not_treated_as_leftover():
    from meal_planner.meal_quality import is_leftover_meal

    meal = Meal(
        name="Miso-Glazed Salmon with Bok Choy",
        slot=MealSlot.DINNER,
        day_label="Wednesday",
        description="Oven-baked salmon with miso and bok choy.",
        ingredients=[
            Ingredient(name="salmon fillets", quantity=400, unit="g"),
            Ingredient(name="miso paste", quantity=2, unit="tablespoons"),
            Ingredient(name="bok choy", quantity=2, unit="each"),
        ],
        steps=["Preheat oven to 200°C.", "Bake salmon until cooked."],
    )
    assert not is_leftover_meal(meal)
    items = build_shopping_ingredients([meal], _profile())
    names = {i.name for i in items}
    linked = [i.name for i in items if meal.name in i.for_meals]
    assert "salmon fillets" in names
    assert "miso paste" in names
    assert "bok choy" in names
    assert linked


def test_leftover_lunch_shops_sides_not_protein():
    from meal_planner.meal_quality import is_leftover_meal, leftover_meal_needs_shop

    assert leftover_meal_needs_shop("mixed salad greens") is True
    assert leftover_meal_needs_shop("cucumber") is True
    assert leftover_meal_needs_shop("tortilla wraps") is True
    assert leftover_meal_needs_shop("eggs") is True
    assert leftover_meal_needs_shop("butter") is True
    assert leftover_meal_needs_shop("grated cheese") is True
    assert leftover_meal_needs_shop("flour") is True
    assert leftover_meal_needs_shop("kimchi") is True
    assert leftover_meal_needs_shop("leftover beef stir-fry") is False
    assert leftover_meal_needs_shop("leftover chicken") is False
    assert leftover_meal_needs_shop("chicken breast") is False
    assert leftover_meal_needs_shop("cooked rice") is False

    leftovers_meal = Meal(
        name="Kimchi Fried Rice with Chicken",
        slot=MealSlot.LUNCH,
        day_label="Tuesday",
        description="Flavorful kimchi fried rice topped with teriyaki chicken leftovers.",
        ingredients=[Ingredient(name="leftover teriyaki chicken", quantity=1)],
        steps=["Top with reheated teriyaki chicken."],
    )
    assert is_leftover_meal(leftovers_meal) is True


def test_dinner_scaled_for_leftovers():
    from meal_planner.meal_quality import scale_dinner_portions_for_leftovers

    dinner = Meal(
        name="Chicken stir fry",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="",
        ingredients=[
            Ingredient(name="chicken breast", quantity=400, unit="g"),
            Ingredient(name="soft taco tortillas", quantity=1, unit="pack"),
            Ingredient(name="cheese", quantity=1, unit="block"),
        ],
        steps=[],
    )
    lunch = Meal(
        name="Leftover chicken wraps",
        slot=MealSlot.LUNCH,
        day_label="Tuesday",
        description="Use leftover chicken from yesterday",
        ingredients=[Ingredient(name="tortilla wraps", quantity=1, unit="pack")],
        steps=["Reheat leftover chicken and wrap."],
    )
    out = scale_dinner_portions_for_leftovers(
        [dinner, lunch], _profile(lunch_mode=LunchMode.PRACTICAL, household_size=2)
    )
    by_name = {i.name: i for i in out[0].ingredients}
    assert by_name["chicken breast"].quantity == 600  # 400 × 1.5, not × household
    assert by_name["soft taco tortillas"].quantity == 1  # packs not doubled
    assert by_name["cheese"].quantity == 1  # cheese blocks not doubled


def test_dinner_not_scaled_without_next_day_leftover_lunch():
    from meal_planner.meal_quality import scale_dinner_portions_for_leftovers

    dinner = Meal(
        name="Beef tacos",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="",
        ingredients=[
            Ingredient(name="beef mince", quantity=500, unit="g"),
            Ingredient(name="soft taco tortillas", quantity=2, unit="pack"),
        ],
        steps=[],
    )
    # Day-1 original lunch — no leftover reuse
    lunch = Meal(
        name="Egg salad sandwich",
        slot=MealSlot.LUNCH,
        day_label="Monday",
        description="Simple first-day lunch",
        ingredients=[Ingredient(name="eggs", quantity=4, unit="each")],
        steps=["Make sandwiches."],
    )
    out = scale_dinner_portions_for_leftovers(
        [dinner, lunch], _profile(lunch_mode=LunchMode.PRACTICAL, household_size=4)
    )
    by_name = {i.name: i for i in out[0].ingredients}
    assert by_name["beef mince"].quantity == 500
    assert by_name["soft taco tortillas"].quantity == 2
