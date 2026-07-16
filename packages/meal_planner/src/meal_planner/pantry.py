"""Pantry items the household already has."""

from __future__ import annotations

from shared.models import Ingredient


def normalize_pantry_item(name: str) -> str:
    return name.strip().lower()


def is_in_pantry(ingredient_name: str, pantry_items: list[str]) -> bool:
    """True if ingredient is already at home (fuzzy substring match)."""
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


def exclude_pantry_ingredients(
    ingredients: list[Ingredient], pantry_items: list[str]
) -> list[Ingredient]:
    """Remove ingredients already at home from the shopping list."""
    if not pantry_items:
        return ingredients
    return [i for i in ingredients if not is_in_pantry(i.name, pantry_items)]
