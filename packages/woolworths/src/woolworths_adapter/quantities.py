"""Normalize recipe ingredient amounts to safe Woolworths cart quantities."""

from __future__ import annotations

import math
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

# Typical piece weights for fresh produce sold loose-by-kg or in bags.
# Used when the recipe asks for N tomatoes/carrots but the catalogue SKU is a bag or $/kg.
_PRODUCE_PIECE_GRAMS: dict[str, float] = {
    "tomato": 120.0,
    "tomatoes": 120.0,
    "carrot": 100.0,
    "carrots": 100.0,
    "onion": 150.0,
    "onions": 150.0,
    "potato": 180.0,
    "potatoes": 180.0,
    "apple": 150.0,
    "apples": 150.0,
    "lemon": 100.0,
    "lemons": 100.0,
    "lime": 60.0,
    "limes": 60.0,
    "orange": 200.0,
    "oranges": 200.0,
    "capsicum": 180.0,
    "courgette": 150.0,
    "zucchini": 150.0,
    "cucumber": 300.0,
}

# Absolute safety caps — prevents runaway cart totals
MAX_EACH_QUANTITY = 12
MAX_KG_QUANTITY = 5.0

_PACK_WEIGHT_RE = re.compile(
    r"(?P<n>\d+(?:\.\d+)?)\s*(?P<u>kg|g)\b",
    re.I,
)


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


def produce_piece_grams(ingredient_name: str) -> float | None:
    """Return typical grams per piece for countable fresh produce, else None."""
    name = ingredient_name.lower().strip()
    if not name:
        return None
    # Cherry / cocktail tomatoes are usually sold as punnets — not individual pieces.
    if "cherry" in name or "grape" in name or "cocktail" in name:
        return None
    if name in _PRODUCE_PIECE_GRAMS:
        return _PRODUCE_PIECE_GRAMS[name]
    # "fresh tomatoes", "red onion"
    for key, grams in _PRODUCE_PIECE_GRAMS.items():
        if re.search(rf"\b{re.escape(key)}\b", name):
            return grams
    return None


def pack_grams_from_product(product: ProductMatch) -> float | None:
    """Parse bag/pack net weight from catalogue size or product name."""
    blob = f"{product.size or ''} {product.product_name or ''}".lower()
    if "per kg" in blob or "/kg" in blob:
        return None
    match = _PACK_WEIGHT_RE.search(blob)
    if not match:
        return None
    n = float(match.group("n"))
    unit = match.group("u").lower()
    grams = n * 1000.0 if unit == "kg" else n
    # Ignore tiny sizes (e.g. spice jars); produce bags are typically ≥150g
    if grams < 150:
        return None
    return grams


def product_is_produce_bag(product: ProductMatch) -> bool:
    """True when an Each-sold produce SKU is a pre-packed bag/bunch, not one loose item."""
    if product.unit == "Kilogram":
        return False
    blob = f"{product.product_name or ''} {product.size or ''}".lower()
    if "per kg" in blob or "loose" in blob:
        return False
    if any(x in blob for x in ("bag", "pack", "punnet", "odd bunch")):
        return True
    # Size like "600g" / "1.5kg" on Each = packed produce (WW tomatoes/carrots)
    return pack_grams_from_product(product) is not None


def _countable_produce_quantity(
    ingredient: Ingredient,
    product: ProductMatch,
    *,
    people: float,
) -> tuple[float, str] | None:
    """Map N produce pieces to kg or bag count. None = not applicable."""
    piece_g = produce_piece_grams(ingredient.name)
    if piece_g is None:
        return None
    unit = _normalize_unit(ingredient.unit)
    qty = float(ingredient.quantity or 0)
    if qty <= 0 or qty >= 50:
        return None
    if unit not in _COUNT_UNITS | {"each", ""}:
        return None

    needed_g = qty * piece_g
    product_unit = product.unit if product.unit in ("Each", "Kilogram") else "Each"

    if product_unit == "Kilogram":
        kg = needed_g / 1000.0
        capped = min(max(0.15, round(kg, 2)), MAX_KG_QUANTITY)
        return capped, "Kilogram"

    pack_g = pack_grams_from_product(product)
    if product_is_produce_bag(product) and pack_g:
        bags = max(1, int(math.ceil(needed_g / pack_g - 1e-9)))
        return float(min(bags, MAX_EACH_QUANTITY)), "Each"

    if product_is_produce_bag(product):
        # Bag/pack without a parseable weight — one pack covers a normal recipe count
        return 1.0, "Each"

    # True loose-each (individual fruit/veg sold as Each)
    base = max(1, int(round(qty)))
    household_cap = max(2, people + 1)
    return float(min(base, MAX_EACH_QUANTITY, household_cap)), "Each"


def normalize_cart_quantity(
    ingredient: Ingredient,
    product: ProductMatch,
    *,
    household_size: float = 2,
) -> tuple[float, str]:
    """
    Convert a recipe ingredient line into a safe Woolworths cart quantity.

    The main bug this fixes: 500g chicken becoming 500x chicken packs in cart.
    ``household_size`` may be adult-equivalent servings (fractional, e.g. 3.5).
    """
    grams = _grams_from_ingredient(ingredient)
    product_unit = product.unit if product.unit in ("Each", "Kilogram") else "Each"

    unit = _normalize_unit(ingredient.unit)
    qty = ingredient.quantity
    name_lower = ingredient.name.lower()
    people = max(1.0, float(household_size or 2))

    produce_qty = _countable_produce_quantity(ingredient, product, people=people)
    if produce_qty is not None:
        return produce_qty

    if grams is not None:
        kg = grams / 1000.0
        if product_unit == "Kilogram":
            capped = min(max(0.15, round(kg, 2)), MAX_KG_QUANTITY)
            # ~150–200g protein per person; salmon is expensive — stay lean
            if "salmon" in name_lower:
                capped = min(capped, round(0.18 * people, 2))
            elif any(p in name_lower for p in ("chicken", "beef", "lamb", "pork", "fish")):
                capped = min(capped, round(0.25 * people, 2))
            return max(0.15, capped), "Kilogram"
        return 1.0, "Each"

    if any(p in name_lower for p in _PANTRY_SINGLE_PACK):
        return 1.0, "Each"

    if unit in _COUNT_UNITS or unit == "each" or product_unit == "Each":
        base = max(1, int(round(qty)))
        is_protein = any(p in name_lower for p in _PROTEIN_TERMS)
        if is_protein:
            # One salmon/fish fillet per person; other proteins up to ~2 pieces each
            if "salmon" in name_lower or "fillet" in name_lower:
                household_cap = people
            else:
                household_cap = min(MAX_EACH_QUANTITY, people * 2)
            return float(min(base, household_cap)), "Each"
        # Countable recipe amount against a kg-priced product (e.g. loose potatoes)
        if product_unit == "Kilogram":
            return min(max(0.15, round(float(base) * 0.15, 2)), MAX_KG_QUANTITY), "Kilogram"
        scaled = min(base, MAX_EACH_QUANTITY)
        household_cap = max(2, people + 1)
        return float(min(scaled, household_cap)), "Each"

    # Unknown unit — safest default is one pack
    return 1.0, product_unit
