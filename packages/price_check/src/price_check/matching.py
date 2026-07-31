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
        "puree",
        "pureed",
        "months",
        "baby",
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
        "imported",
        "head",
        "fillet",
        "fillets",
        "leaf",
        "leaves",
    }
)

# NZ / common grocery aliases (any token in a group matches the others).
_ALIAS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"zucchini", "courgette", "courgettes"}),
    frozenset({"coriander", "cilantro"}),
    frozenset({"swede", "rutabaga"}),
)

# Alternate search queries when the literal ingredient name is a poor catalogue query.
_SEARCH_VARIANTS: dict[str, tuple[str, ...]] = {
    "broccoli head": ("broccoli",),
    "zucchini": ("courgette", "courgettes"),
    "courgette": ("zucchini",),
    "mixed salad greens": ("mixed leaf salad", "mesclun", "salad mix", "mixed salad", "salad leaves"),
    "salad greens": ("mesclun", "mixed leaf salad", "salad mix", "salad leaves"),
    "fish fillets": ("white fish fillets", "fish fillet"),
    "snap peas": ("sugar snap peas", "sugarsnap peas", "snow peas"),
    "avocado": ("fresh avocado", "avocados"),
    "stir fry vegetables": (
        "stir fry veg",
        "mixed vegetables",
        "stirfry vegetables",
        "asian stir fry",
        "frozen stir fry",
    ),
    "vegetable stock": ("vegetable stock liquid", "vegetable stock powder"),
    "wholegrain wraps": ("wholemeal wraps", "whole grain wraps"),
    "wholegrain bread": ("wholemeal bread", "whole grain bread"),
}

# Substrings in a product name that count as a hit for a phrase ingredient.
_PHRASE_ACCEPT: dict[str, tuple[str, ...]] = {
    "mixed salad greens": (
        "mesclun",
        "mixed leaf",
        "mixed salad",
        "salad leaves",
        "salad leaf",
        "baby leaf",
        "garden salad",
    ),
    "salad greens": (
        "mesclun",
        "mixed leaf",
        "salad leaves",
        "salad leaf",
        "baby leaf",
    ),
    "snap peas": ("sugar snap pea", "sugarsnap pea", "snap pea"),
}

# Ingredient-specific rejects (substring in product name).
_INGREDIENT_REJECT: dict[str, tuple[str, ...]] = {
    "avocado": ("kit", "ranch", "salad", "dip", "guacamole", "oil", "dressing"),
    "milk": ("coconut", "almond", "oat", "soy", "powder", "chocolate", "condensed", "evaporated"),
    "chicken breast": ("nugget", "tender", "crumb", "schnitzel", "pie", "stock", "broth"),
    "chicken thigh": ("nugget", "tenderbasted", "crumb", "schnitzel", "pie", "stock", "broth"),
    "chicken thighs": ("nugget", "tenderbasted", "crumb", "schnitzel", "pie", "stock", "broth"),
    "beef mince": ("pork", "chicken", "lamb", "sausage", "pie", "patty", "burger"),
    "beef": ("pork", "chicken", "lamb", "sausage"),
    "broccoli": ("bite", "bites", "cheese", "soup", "kit", "salad", "rice"),
    "broccoli head": ("bite", "bites", "cheese", "soup", "kit", "salad", "rice"),
    "zucchini": ("puree", "pureed", "months", "baby", "quinoa"),
    "courgette": ("puree", "pureed", "months", "baby", "quinoa"),
    "snap peas": ("crisp", "crisps", "harvest", "shoot", "shoots", "mix", "steam"),
    "snap pea": ("crisp", "crisps", "harvest", "shoot", "shoots", "mix", "steam"),
    "rice": ("cracker", "cake", "milk", "wine", "vinegar", "paper", "pudding"),
    "onion": ("powder", "salt", "soup", "dip", "rings"),
    "garlic": ("salt", "powder", "sauce", "bread", "aioli"),
    "egg": ("noodle", "plant", "tofu", "mayonnaise", "mayo"),
    "butter": ("chicken", "cookie", "peanut", "almond"),
    "flour": ("tortilla", "wrap", "self raising mix"),
    "tomato": ("sauce", "paste", "ketchup", "soup", "juice", "passata"),
    "potato": ("chip", "crisp", "mash mix", "waffle"),
    "cheese": ("cake", "ball", "sauce", "spread", "roll", "stick", "sticks"),
    "honey": ("cashew", "roasted", "mustard", "nut", "nuts", "cereal"),
    "salsa": ("chip", "crisp", "grainwave", "sunbite", "twistie", "cracker"),
    "stir fry vegetables": ("sauce", "noodle", "seasoning", "kit"),
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1}


def _expand_aliases(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for group in _ALIAS_GROUPS:
        if tokens & group:
            expanded |= group
    return expanded


def search_query_variants(ingredient: str) -> list[str]:
    """Ordered unique search strings to try against a catalogue."""
    ing = ingredient.strip()
    if not ing:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for q in (ing, *(_SEARCH_VARIANTS.get(ing.lower(), ()))):
        key = q.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(q.strip())
    # Drop trailing size/form words for a last-resort simpler query.
    simplified = re.sub(
        r"\b(head|fillets|fillet|leaves|leaf|bunch|fresh)\b",
        "",
        ing,
        flags=re.I,
    )
    simplified = re.sub(r"\s+", " ", simplified).strip()
    if simplified and simplified.lower() not in seen:
        out.append(simplified)
    return out


def _rejected_for_ingredient(ingredient: str, product_blob: str) -> bool:
    ing = ingredient.lower().strip()
    blob = product_blob.lower()
    for key, needles in _INGREDIENT_REJECT.items():
        if ing == key or ing.startswith(key) or key.startswith(ing):
            # Skip needles that are part of the ingredient itself
            # (e.g. "egg"→"noodle" must not reject "egg noodles").
            active = tuple(n for n in needles if n not in ing)
            if active and any(n in blob for n in active):
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

    phrase_hit = any(p in prod for p in _PHRASE_ACCEPT.get(ing, ()))
    # Dressed / kit salads are still wrong even if they mention mesclun.
    if phrase_hit and any(bad in prod for bad in ("dressing", "kit", "crispy salad")):
        phrase_hit = False

    ing_tokens = _tokens(ing)
    prod_tokens = _tokens(prod)
    if not ing_tokens:
        return 0.0

    ing_exp = _expand_aliases(ing_tokens)
    prod_exp = _expand_aliases(prod_tokens)

    # Reject prepared foods that only mention the ingredient in passing.
    # Tokens that appear in the ingredient itself are allowed (e.g. "salad greens").
    active_junk = _JUNK_TOKENS - ing_exp
    meaningful_extra = prod_exp - ing_exp - _FILLER_TOKENS
    if meaningful_extra & active_junk and not phrase_hit:
        return 0.0

    overlap = ing_exp & prod_exp
    if (
        not overlap
        and not phrase_hit
        and ing not in prod
        and not any(a in prod for a in ing_exp if len(a) > 3)
    ):
        return 0.0

    ratio = len(overlap) / len(ing_exp) if ing_exp else 0.0
    synonym_hit = bool((ing_exp - ing_tokens) & prod_exp) or bool((prod_exp - prod_tokens) & ing_exp)
    if phrase_hit:
        synonym_hit = True
        ratio = max(ratio, 0.6)
    if ing not in prod and ratio < 0.5 and not synonym_hit:
        return 0.0
    if synonym_hit and ratio < 0.34:
        # zucchini ↔ courgette: single-token synonym match is enough
        if len(ing_tokens) <= 2 and overlap:
            ratio = max(ratio, 0.5)
        else:
            return 0.0

    non_filler = prod_exp - _FILLER_TOKENS
    tightness = len(overlap) / max(1, len(non_filler)) if non_filler else ratio

    if ing in prod or ing == prod_raw or synonym_hit or phrase_hit:
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
