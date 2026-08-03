"""Pantry staples: owned vs opted-in to buy."""

from __future__ import annotations

from shared.models import Ingredient, Meal


def normalize_pantry_item(name: str) -> str:
    return name.strip().lower()


def is_in_pantry(ingredient_name: str, pantry_items: list[str]) -> bool:
    """True if ingredient matches a pantry list entry (fuzzy substring match)."""
    if not pantry_items:
        return False
    name = ingredient_name.lower().strip()
    for item in pantry_items:
        p = normalize_pantry_item(item)
        if not p:
            continue
        if p == name or p in name or name in p:
            return True
        # word overlap e.g. pantry "olive oil" vs ingredient "extra virgin olive oil"
        p_words = set(p.split())
        n_words = set(name.split())
        if p_words and p_words.issubset(n_words):
            return True
    return False


def is_owned_pantry(
    ingredient: Ingredient, pantry_to_buy: list[str] | None = None
) -> bool:
    """True when ingredient is a pantry staple the household is keeping (not buying)."""
    if not ingredient.is_pantry:
        return False
    return not is_in_pantry(ingredient.name, pantry_to_buy or [])


def exclude_owned_pantry_ingredients(
    ingredients: list[Ingredient], pantry_to_buy: list[str] | None = None
) -> list[Ingredient]:
    """Drop pantry staples that the user has not ticked to buy."""
    return [i for i in ingredients if not is_owned_pantry(i, pantry_to_buy)]


def exclude_pantry_ingredients(
    ingredients: list[Ingredient], pantry_items: list[str]
) -> list[Ingredient]:
    """Deprecated: profile pantry list exclusion. Prefer exclude_owned_pantry_ingredients."""
    if not pantry_items:
        return ingredients
    return [i for i in ingredients if not is_in_pantry(i.name, pantry_items)]


def collect_required_pantry(meals: list) -> list[str]:
    """First-seen deduped pantry-tagged ingredient names across meals."""
    seen: set[str] = set()
    ordered: list[str] = []
    for meal in meals:
        for ing in getattr(meal, "ingredients", None) or []:
            if not getattr(ing, "is_pantry", False):
                continue
            name = normalize_pantry_item(getattr(ing, "name", "") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            ordered.append(name)
    return ordered


def pantry_uses_note(meal: Meal) -> str | None:
    """Light per-recipe note listing that meal's pantry staples."""
    names = collect_required_pantry([meal])
    if not names:
        return None
    return "Uses pantry: " + ", ".join(names)
