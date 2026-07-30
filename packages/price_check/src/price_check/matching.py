"""Simple product name matching for price-check adapters."""

from __future__ import annotations

import re

# Extra product tokens that usually mean a prepared / flavoured / wrong SKU.
_JUNK_TOKENS = frozenset(
    {
        "kit",
        "salad",
        "ranch",
        "dip",
        "guacamole",
        "juice",
        "drink",
        "smoothie",
        "yoghurt",
        "yogurt",
        "sauce",
        "seasoning",
        "marinade",
        "stock",
        "broth",
        "nugget",
        "nuggets",
        "tender",
        "tenders",
        "crumb",
        "crumbed",
        "schnitzel",
        "pie",
        "cracker",
        "crackers",
        "cake",
        "wine",
        "vinegar",
        "powder",
        "chips",
        "crisps",
        "ready",
        "meal",
        "soup",
        "aioli",
        "mayonnaise",
        "mayo",
        "chocolate",
        "condensed",
        "evaporated",
        "coconut",
        "almond",
        "oat",
        "soy",
        "plant",
        "tofu",
        "tortilla",
        "wrap",
        "cookie",
        "cookies",
        "peanut",
        "hummus",
        "pesto",
        "salsa",
        "dressing",
        "chopped",
        "bites",
        "bite",
        "nibble",
        "nibbles",
        "fritter",
        "fritters",
        "quiche",
        "bake",
        "gratin",
    }
)

# Tokens that are fine to ignore when scoring tightness.
_FILLER_TOKENS = frozenset(
    {
        "nz",
        "new",
        "zealand",
        "fresh",
        "organic",
        "free",
        "range",
        "kg",
        "g",
        "gm",
        "ml",
        "l",
        "pack",
        "pk",
        "ea",
        "each",
        "min",
        "order",
        "woolworths",
        "countdown",
        "paknsave",
        "pak",
        "n",
        "save",
        "newworld",
        "world",
        "freshchoice",
        "premium",
        "select",
        "value",
        "standard",
        "anchor",
        "pams",
        "homebrand",
        "budget",
        "skinless",
        "boneless",
        "trimmed",
        "whole",
        "loose",
        "pre",
        "ripened",
        "ripe",
        "certified",
        "bostock",
        "brothers",
        "percent",
        "100",
    }
)

# Ingredient-specific rejects (substring in product name).
_INGREDIENT_REJECT: dict[str, tuple[str, ...]] = {
    "avocado": ("kit", "ranch", "salad", "dip", "guacamole", "oil", "dressing"),
    "milk": ("coconut", "almond", "oat", "soy", "powder", "chocolate", "condensed", "evaporated"),
    "chicken breast": ("nugget", "tender", "crumb", "schnitzel", "pie", "stock", "broth"),
    "chicken thigh": ("nugget", "crumb", "schnitzel", "pie", "stock"),
    "beef mince": ("pork", "chicken", "lamb", "sausage", "pie", "patty", "burger"),
    "beef": ("pork", "chicken", "lamb", "sausage"),
    "broccoli": ("bite", "bites", "cheese", "soup", "kit", "salad", "rice"),
    "broccoli head": ("bite", "bites", "cheese", "soup", "kit", "salad", "rice"),
    "rice": ("cracker", "cake", "milk", "wine", "vinegar", "paper", "pudding"),
    "onion": ("powder", "salt", "soup", "dip", "rings"),
    "garlic": ("salt", "powder", "sauce", "bread", "aioli"),
    "egg": ("noodle", "plant", "tofu", "mayonnaise", "mayo"),
    "butter": ("chicken", "cookie", "peanut", "almond"),
    "flour": ("tortilla", "wrap", "self raising mix"),
    "tomato": ("sauce", "paste", "ketchup", "soup", "juice", "passata"),
    "potato": ("chip", "crisp", "mash mix", "waffle"),
    "cheese": ("cake", "ball", "sauce", "spread"),
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1}


def _rejected_for_ingredient(ingredient: str, product_blob: str) -> bool:
    ing = ingredient.lower().strip()
    blob = product_blob.lower()
    for key, needles in _INGREDIENT_REJECT.items():
        if ing == key or ing.startswith(key) or key.startswith(ing):
            if any(n in blob for n in needles):
                return True
    return False


def score_product_name(ingredient: str, product_name: str, brand: str = "") -> float:
    """Higher is better. 0 means reject."""
    ing = ingredient.lower().strip()
    prod_raw = product_name.lower().strip()
    prod = f"{brand} {product_name}".lower().strip()
    if not ing or not prod_raw:
        return 0.0
    if _rejected_for_ingredient(ing, prod):
        return 0.0
    if ing == prod_raw:
        return 100.0

    ing_tokens = _tokens(ing)
    prod_tokens = _tokens(prod)
    if not ing_tokens:
        return 0.0

    # Reject prepared foods that only mention the ingredient in passing.
    meaningful_extra = prod_tokens - ing_tokens - _FILLER_TOKENS
    if meaningful_extra & _JUNK_TOKENS:
        return 0.0

    overlap = ing_tokens & prod_tokens
    if not overlap and ing not in prod:
        return 0.0

    ratio = len(overlap) / len(ing_tokens) if ing_tokens else 0.0
    if ing not in prod and ratio < 0.5:
        return 0.0

    # Prefer tighter product names (avocado > avocado ranch kit, already rejected).
    non_filler = prod_tokens - _FILLER_TOKENS
    tightness = len(overlap) / max(1, len(non_filler)) if non_filler else ratio

    if ing in prod or ing == prod_raw:
        return 75.0 + 20.0 * tightness + min(5.0, len(ing) * 0.2)
    return 40.0 + 35.0 * ratio + 15.0 * tightness


def pick_best_product(
    ingredient: str,
    candidates: list[dict],
    *,
    name_key: str = "name",
    brand_key: str = "brand",
) -> dict | None:
    best: tuple[float, dict] | None = None
    for cand in candidates:
        name = str(cand.get(name_key) or "")
        brand = str(cand.get(brand_key) or "")
        score = score_product_name(ingredient, name, brand)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, cand)
    return best[1] if best else None
