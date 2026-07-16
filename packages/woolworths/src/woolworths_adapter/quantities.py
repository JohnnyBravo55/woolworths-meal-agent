"""Normalize recipe ingredient amounts to safe Woolworths cart quantities."""

from __future__ import annotations

import re

from shared.models import Ingredient, ProductMatch

# Units that represent weight — recipe amounts must NOT become "500 Each"
_WEIGHT_UNITS = frozenset({"g", "gram", "grams", "kg", "kilogram", "kilograms", "kilo"})

# Units that represent countable items
_COUNT_UNITS = frozenset(
    {
        "each",
        "piece",
        "pieces",
        "fillet",
        "fillets",
        "can",
        "cans",
        "pack",
        "packs",
        "bag",
        "bags",
        "bunch",
        "head",
        "jar",
        "bottle",
        "block",
        "tub",
        "punnet",
        "loaf",
        "sheets",
        "sheet",
        "clove",
        "cloves",
        "sprig",
        "sprigs",
    }
)

# Sauces/oils/pastes/grains — one pack per shop even if many meals use them
_PANTRY_SINGLE_PACK = frozenset(
    {
        "soy sauce",
        "olive oil",
        "honey",
        "mayonnaise",
        "salsa",
        "pasta sauce",
        "gravy",
        "lemon juice",
        "hummus",
        "miso paste",
        "miso",
        "green curry paste",
        "red curry paste",
        "curry paste",
        "quinoa",
        "rice vinegar",
        "balsamic vinegar",
        "sesame oil",
        "fish sauce",
        "oyster sauce",
        "teriyaki sauce",
    }
)

# Protein / fillet lines — respect recipe counts for household
_PROTEIN_TERMS = frozenset(
    {
        "salmon",
        "chicken",
        "beef",
        "fish",
        "pork",
        "lamb",
        "tofu",
        "fillet",
        "fillets",
        "mince",
        "steak",
        "prawn",
        "egg",
    }
)

# Absolute safety caps — prevents runaway cart totals
MAX_EACH_QUANTITY = 12
MAX_KG_QUANTITY = 5.0


def _normalize_unit(unit: str) -> str:
    return unit.lower().strip().replace(".", "")


def _is_weight_unit(unit: str) -> bool:
    u = _normalize_unit(unit)
    if u in _WEIGHT_UNITS:
        return True
    # "500g" style combined strings
    return bool(re.fullmatch(r"\d+\s*(g|kg|gram|grams)", u))


def _grams_from_ingredient(ingredient: Ingredient) -> float | None:
    """Convert ingredient amount to grams if it is a weight measurement."""
    unit = _normalize_unit(ingredient.unit)
    qty = ingredient.quantity

    if unit in {"g", "gram", "grams"}:
        return qty
    if unit in {"kg", "kilogram", "kilograms", "kilo"}:
        return qty * 1000

    # Heuristic: large quantity with count-ish unit is probably grams (LLM mistake)
    if qty >= 50 and unit in _COUNT_UNITS | {"each", ""}:
        return qty

    return None


def normalize_cart_quantity(
    ingredient: Ingredient,
    product: ProductMatch,
    *,
    household_size: int = 2,
) -> tuple[float, str]:
    """
    Convert a recipe ingredient line into a safe Woolworths cart quantity.

    The main bug this fixes: 500g chicken becoming 500x chicken packs in cart.
    """
    grams = _grams_from_ingredient(ingredient)
    product_unit = product.unit if product.unit in ("Each", "Kilogram") else "Each"

    if grams is not None:
        kg = grams / 1000.0
        if product_unit == "Kilogram":
            capped = min(max(0.15, round(kg, 2)), MAX_KG_QUANTITY)
            return capped, "Kilogram"
        return 1.0, "Each"

    unit = _normalize_unit(ingredient.unit)
    qty = ingredient.quantity
    name_lower = ingredient.name.lower()

    if any(p in name_lower for p in _PANTRY_SINGLE_PACK):
        return 1.0, "Each"

    if unit in _COUNT_UNITS or unit == "each" or product_unit == "Each":
        base = max(1, int(round(qty)))
        is_protein = any(p in name_lower for p in _PROTEIN_TERMS)
        if is_protein:
            # Recipe may already include leftover scaling — honour count, cap sanely
            household_cap = min(MAX_EACH_QUANTITY, max(household_size * 2, int(round(qty))))
            return float(min(base, household_cap)), "Each"
        scaled = min(base, MAX_EACH_QUANTITY)
        household_cap = max(2, household_size + 1)
        return float(min(scaled, household_cap)), "Each"

    # Unknown unit — safest default is one pack
    return 1.0, product_unit
