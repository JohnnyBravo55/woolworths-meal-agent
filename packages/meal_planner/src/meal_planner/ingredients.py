"""Ingredient list utilities."""

from __future__ import annotations

from shared.allergy import ingredient_conflicts_allergies, normalize_mandatory_for_allergies
from shared.models import Ingredient, UserProfile

from meal_planner.ingredient_normalize import normalize_ingredient_name
from meal_planner.meal_quality import is_leftover_meal, leftover_meal_needs_shop
from meal_planner.pantry import exclude_pantry_ingredients, is_in_pantry
from meal_planner.shop_coverage import link_meals_to_shop_items, repair_shop_coverage

# When the same protein appears on multiple dinners, buy the largest line — not a sum
_MAX_WHEN_MERGING = frozenset(
    {
        "salmon",
        "salmon fillet",
        "salmon fillets",
        "fish fillets",
        "chicken breast",
        "chicken thighs",
        "beef mince",
        "beef strips",
        "tofu",
        "eggs",
    }
)


def filter_allergens(ingredients: list[Ingredient], profile: UserProfile) -> list[Ingredient]:
    """Remove ingredients that conflict with declared allergies."""
    if not profile.allergies:
        return ingredients
    return [i for i in ingredients if not ingredient_conflicts_allergies(i.name, profile)]


def build_shopping_ingredients(meals: list, profile: UserProfile) -> list[Ingredient]:
    """Flatten meal ingredients, apply mandatory items, allergy and pantry filters."""
    from shared.models import Meal

    mandatory = normalize_mandatory_for_allergies(profile.mandatory_items, profile)
    items = collect_plan_ingredients(meals, mandatory)
    items = filter_allergens(items, profile)
    items = exclude_pantry_ingredients(items, profile.pantry_items)
    items = _ensure_meal_ingredients_present(meals, items, profile)
    items = link_meals_to_shop_items(meals, items, profile)
    items = repair_shop_coverage(meals, items, profile)
    return _prune_orphan_ingredients(items, meals, mandatory)


def _prune_orphan_ingredients(
    items: list[Ingredient],
    meals: list,
    mandatory: list[str],
) -> list[Ingredient]:
    """Drop shop lines not tied to any meal (unless mandatory)."""
    from shared.models import Meal

    meal_names = {m.name for m in meals if isinstance(m, Meal)}
    mandatory_norm = {normalize_ingredient_name(m) for m in mandatory}
    kept: list[Ingredient] = []
    for item in items:
        if item.is_mandatory or normalize_ingredient_name(item.name) in mandatory_norm:
            kept.append(item)
            continue
        linked = [m for m in item.for_meals if m in meal_names or m == "mandatory"]
        if linked:
            kept.append(item)
    return kept


def _ensure_meal_ingredients_present(
    meals: list,
    items: list[Ingredient],
    profile: UserProfile,
) -> list[Ingredient]:
    """Every ingredient listed on a meal must appear on the shop list."""
    from shared.models import Ingredient, Meal

    on_list = {normalize_ingredient_name(i.name) for i in items}
    extras: list[Ingredient] = []
    for meal in meals:
        if not isinstance(meal, Meal):
            continue
        if is_leftover_meal(meal):
            for ing in meal.ingredients:
                norm = normalize_ingredient_name(ing.name)
                if not leftover_meal_needs_shop(norm):
                    continue
                if is_in_pantry(norm, profile.pantry_items):
                    continue
                if norm not in on_list:
                    copy = ing.model_copy(deep=True)
                    copy.name = norm
                    if meal.name not in copy.for_meals:
                        copy.for_meals.append(meal.name)
                    extras.append(copy)
                    on_list.add(norm)
            continue
        for ing in meal.ingredients:
            norm = normalize_ingredient_name(ing.name)
            if is_in_pantry(norm, profile.pantry_items):
                continue
            if norm not in on_list:
                copy = ing.model_copy(deep=True)
                copy.name = norm
                if meal.name not in copy.for_meals:
                    copy.for_meals.append(meal.name)
                extras.append(copy)
                on_list.add(norm)
    return deduplicate_ingredients(items + extras)


def deduplicate_ingredients(ingredients: list[Ingredient]) -> list[Ingredient]:
    """Merge duplicate ingredients across meals by normalized name."""
    merged: dict[str, Ingredient] = {}

    for ingredient in ingredients:
        name = normalize_ingredient_name(ingredient.name)
        ingredient = ingredient.model_copy(deep=True)
        ingredient.name = name
        key = name
        if key not in merged:
            merged[key] = ingredient
            continue

        existing = merged[key]
        if key in _MAX_WHEN_MERGING:
            existing.quantity = max(existing.quantity, ingredient.quantity)
        else:
            existing.quantity += ingredient.quantity
        for meal in ingredient.for_meals:
            if meal not in existing.for_meals:
                existing.for_meals.append(meal)
        if ingredient.notes and ingredient.notes not in existing.notes:
            existing.notes = f"{existing.notes}; {ingredient.notes}".strip("; ")

    return list(merged.values())


def collect_plan_ingredients(meals: list, mandatory: list[str] | None = None) -> list[Ingredient]:
    """Flatten meal ingredients and add mandatory items."""
    from shared.models import Ingredient, Meal

    items: list[Ingredient] = []

    for meal in meals:
        if not isinstance(meal, Meal):
            continue
        if is_leftover_meal(meal):
            for ing in meal.ingredients:
                norm = normalize_ingredient_name(ing.name)
                if not leftover_meal_needs_shop(norm):
                    continue
                copy = ing.model_copy(deep=True)
                copy.name = norm
                if meal.name not in copy.for_meals:
                    copy.for_meals.append(meal.name)
                items.append(copy)
            continue
        for ing in meal.ingredients:
            copy = ing.model_copy(deep=True)
            copy.name = normalize_ingredient_name(copy.name)
            # Never buy ingredients explicitly labeled as leftovers
            if copy.name.startswith(
                ("leftover ", "left over ", "left-over ", "steamed ")
            ):
                continue
            if meal.name not in copy.for_meals:
                copy.for_meals.append(meal.name)
            items.append(copy)

    for name in mandatory or []:
        items.append(
            Ingredient(
                name=name,
                quantity=1.0,
                unit="each",
                is_mandatory=True,
                for_meals=["mandatory"],
            )
        )

    return deduplicate_ingredients(items)
