"""Tests for meal-plan → shop-list coverage audit and repair."""

from meal_planner.ingredients import build_shopping_ingredients
from meal_planner.planner import _build_plan_shopping_list, _enforce_meal_counts
from meal_planner.shop_coverage import (
    audit_shop_coverage,
    heal_resolved_coverage,
    infer_ingredients_from_titles,
)
from shared.models import (
    GroceryLineItem,
    Ingredient,
    LunchMode,
    Meal,
    MealPlan,
    MealSlot,
    MealsRequested,
    UserProfile,
)


def _profile(**kwargs) -> UserProfile:
    defaults = dict(
        household_size=2,
        meals_requested=MealsRequested(dinner=6, lunch=4, snacks=3),
        budget_nzd=250,
        allergies=["gluten"],
        mandatory_items=["gluten free bread", "milk"],
        pantry_items=[
            "soy sauce",
            "olive oil",
            "salt",
            "pepper",
            "lemon juice",
            "onions",
            "garlic",
        ],
        lunch_mode=LunchMode.PRACTICAL,
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _ing(name: str, quantity: float = 1.0, unit: str = "each") -> Ingredient:
    return Ingredient(name=name, quantity=quantity, unit=unit)


def _export_like_plan() -> MealPlan:
    meals = [
        Meal(
            name="Teriyaki Chicken with Rice and Broccoli",
            slot=MealSlot.DINNER,
            day_label="Monday",
            description="",
            ingredients=[
                _ing("chicken thighs", 0.8, "kg"),
                _ing("gluten-free teriyaki sauce"),
                _ing("rice"),
                _ing("broccoli head"),
            ],
            steps=[],
        ),
        Meal(
            name="Beef Stir-Fry with Capsicum and Rice",
            slot=MealSlot.DINNER,
            day_label="Tuesday",
            description="",
            ingredients=[
                _ing("beef strips"),
                _ing("capsicum", 2),
                _ing("rice"),
                _ing("broccoli head"),
                _ing("gluten-free oyster sauce"),
            ],
            steps=[],
        ),
        Meal(
            name="Green Curry Chicken with Jasmine Rice",
            slot=MealSlot.DINNER,
            day_label="Wednesday",
            description="",
            ingredients=[
                _ing("chicken thighs", 0.8, "kg"),
                _ing("green curry paste"),
                _ing("coconut milk"),
                _ing("jasmine rice"),
                _ing("capsicum"),
            ],
            steps=[],
        ),
        Meal(
            name="Grilled Chicken Thighs with Roasted Vegetables",
            slot=MealSlot.DINNER,
            day_label="Thursday",
            description="Succulent grilled chicken served with roasted vegetables.",
            ingredients=[],
            steps=[],
        ),
        Meal(
            name="Hero Dinner: Thai Beef Massaman Curry",
            slot=MealSlot.DINNER,
            day_label="Friday",
            description="Rich Massaman curry made with tender beef.",
            ingredients=[
                _ing("massaman curry paste", 2),
                _ing("coconut milk"),
                _ing("jasmine rice"),
                _ing("potato", 2),
                _ing("broccoli"),
            ],
            steps=[],
        ),
        Meal(
            name="Grilled Chicken with Quinoa Salad",
            slot=MealSlot.DINNER,
            day_label="Saturday",
            description="",
            ingredients=[
                _ing("chicken breasts", 0.8, "kg"),
                _ing("quinoa", 2),
                _ing("cucumber"),
                _ing("cherry tomatoes"),
            ],
            steps=[],
        ),
    ]
    plan = MealPlan(meals=meals)
    plan = _enforce_meal_counts(plan, _profile())
    return _build_plan_shopping_list(plan, _profile())


def _linked_meals(items, meal_name: str) -> list[str]:
    return [i.name for i in items if meal_name in i.for_meals]


def test_orphaned_thursday_dinner_gets_shop_items():
    plan = _export_like_plan()
    thursday = next(m for m in plan.meals if m.day_label == "Thursday")
    linked = _linked_meals(plan.shared_ingredients, thursday.name)
    assert linked, f"Thursday dinner should have shop items, got none; ingredients={thursday.ingredients}"
    assert audit_shop_coverage(plan.meals, plan.shared_ingredients, _profile()) == []


def test_massaman_gets_beef_not_chicken():
    plan = _export_like_plan()
    friday = next(m for m in plan.meals if m.day_label == "Friday")
    ingredient_names = {i.name for i in friday.ingredients}
    assert "beef strips" in ingredient_names
    shop_names = {i.name for i in plan.shared_ingredients}
    assert "beef strips" in shop_names
    assert friday.name in next(
        i for i in plan.shared_ingredients if i.name == "beef strips"
    ).for_meals


def test_pantry_only_dinner_still_gets_shop_items():
    profile = _profile()
    meal = Meal(
        name="Grilled Chicken Thighs with Roasted Vegetables",
        slot=MealSlot.DINNER,
        day_label="Thursday",
        description="Grilled chicken with roasted vegetables.",
        ingredients=[_ing("olive oil"), _ing("salt"), _ing("pepper"), _ing("garlic")],
        steps=[],
    )
    infer_ingredients_from_titles([meal], profile)
    items = build_shopping_ingredients([meal], profile)
    linked = _linked_meals(items, meal.name)
    assert linked
    assert audit_shop_coverage([meal], items, profile) == []


def test_infer_beef_from_meal_title():
    profile = _profile()
    meal = Meal(
        name="Hero Dinner: Thai Beef Massaman Curry",
        slot=MealSlot.DINNER,
        day_label="Friday",
        description="Made with tender beef.",
        ingredients=[_ing("massaman curry paste"), _ing("coconut milk")],
        steps=[],
    )
    infer_ingredients_from_titles([meal], profile)
    names = {i.name for i in meal.ingredients}
    assert "beef strips" in names


def test_stuffed_capsicum_shops_chicken_not_cooked_label():
    profile = _profile()
    meal = Meal(
        name="Stuffed Capsicum",
        slot=MealSlot.DINNER,
        day_label="Friday",
        description="Capsicum stuffed with chicken and rice.",
        ingredients=[
            _ing("capsicum", 4),
            _ing("cooked chicken", 200, "g"),
            _ing("brown rice", 1, "cup"),
        ],
        steps=["Stuff capsicum and bake."],
    )
    items = build_shopping_ingredients([meal], profile)
    names = {i.name for i in items}
    assert "chicken breast" in names
    assert meal.name in next(i for i in items if i.name == "chicken breast").for_meals
    assert "capsicum" in names
    assert audit_shop_coverage([meal], items, profile) == []


def test_leftover_lunch_still_shops_salad_greens():
    profile = _profile(lunch_mode=LunchMode.ORIGINAL)
    lunch = Meal(
        name="Beef Stir-Fry Salad",
        slot=MealSlot.LUNCH,
        day_label="Tuesday",
        description="Fresh salad with leftover beef stir-fry.",
        ingredients=[
            _ing("leftover beef stir-fry", 300, "g"),
            _ing("mixed salad greens", 2, "cups"),
            _ing("cucumber", 1),
        ],
        steps=["Combine leftover beef with salad greens."],
    )
    items = build_shopping_ingredients([lunch], profile)
    names = {i.name for i in items}
    assert "mixed salad greens" in names
    assert "cucumber" in names
    assert "leftover beef stir-fry" not in names
    assert lunch.name in next(i for i in items if i.name == "mixed salad greens").for_meals


def test_leftover_frittata_shops_eggs():
    profile = _profile(lunch_mode=LunchMode.PRACTICAL)
    lunch = Meal(
        name="Pasta Leftover Frittata",
        slot=MealSlot.LUNCH,
        day_label="Tuesday",
        description="Hearty frittata using leftover pasta.",
        ingredients=[
            _ing("leftover pasta with tomato and spinach", 1, "plate"),
            _ing("eggs", 4, "units"),
        ],
        steps=["Whisk eggs with leftover pasta and bake."],
    )
    items = build_shopping_ingredients([lunch], profile)
    names = {i.name for i in items}
    assert "eggs" in names
    assert "leftover pasta with tomato and spinach" not in names
    assert lunch.name in next(i for i in items if i.name == "eggs").for_meals


def test_leftover_lunch_links_reused_dinner_ingredients():
    profile = _profile(lunch_mode=LunchMode.PRACTICAL)
    dinner = Meal(
        name="Pasta al Pomodoro",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="Classic tomato pasta.",
        ingredients=[
            _ing("pasta", 400, "g"),
            _ing("tinned tomatoes", 1, "can"),
            _ing("basil", 1, "bunch"),
            _ing("parmesan cheese", 100, "g"),
        ],
        steps=["Cook pasta with sauce."],
    )
    lunch = Meal(
        name="Pasta al Pomodoro Salad",
        slot=MealSlot.LUNCH,
        day_label="Tuesday",
        description="Cold pasta salad using leftover pasta al pomodoro.",
        ingredients=[
            _ing("pasta", 200, "g"),
            _ing("tinned tomatoes", 0.5, "can"),
            _ing("basil", 1, "bunch"),
            _ing("parmesan cheese", 50, "g"),
        ],
        steps=["Toss leftover pasta cold."],
    )
    items = build_shopping_ingredients([dinner, lunch], profile)
    pasta = next(i for i in items if i.name == "pasta")
    assert dinner.name in pasta.for_meals
    assert lunch.name in pasta.for_meals


def test_heal_does_not_add_offline_for_sku_merged_slash_name():
    """SKU merge names lines 'carrot / carrots'; heal must still see coverage."""
    profile = _profile()
    meal = Meal(
        name="Stew",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="Veg stew",
        ingredients=[_ing("carrot", 2, "each"), _ing("carrots", 2, "each")],
        steps=["Cook"],
    )
    merged = GroceryLineItem(
        ingredient="carrot / carrots",
        sku="135369",
        product_name="woolworths carrots",
        quantity=4.0,
        unit="Each",
        unit_price=2.79,
        line_total=11.16,
        for_meals=[meal.name],
        in_stock=True,
    )
    healed, issues = heal_resolved_coverage([meal], [merged], profile)
    assert not any(i.sku == "OFFLINE" for i in healed)
    assert not issues
