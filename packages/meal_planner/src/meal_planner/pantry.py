"""Pantry staples: owned vs opted-in to buy."""

from __future__ import annotations

import re

from shared.models import Ingredient, Meal

# Exact / near-exact household staples the recipes checklist should always surface.
_PANTRY_EXACT = frozenset(
    {
        "salt",
        "pepper",
        "black pepper",
        "white pepper",
        "sugar",
        "brown sugar",
        "caster sugar",
        "honey",
        "soy sauce",
        "fish sauce",
        "oyster sauce",
        "teriyaki sauce",
        "sweet chilli",
        "sweet chilli sauce",
        "sesame oil",
        "olive oil",
        "vegetable oil",
        "canola oil",
        "rice vinegar",
        "balsamic vinegar",
        "white vinegar",
        "apple cider vinegar",
        "cumin",
        "ground cumin",
        "paprika",
        "smoked paprika",
        "garlic powder",
        "onion powder",
        "dried oregano",
        "dried thyme",
        "dried basil",
        "mixed herbs",
        "italian herbs",
        "curry powder",
        "garam masala",
        "turmeric",
        "chilli flakes",
        "chili flakes",
        "red chilli flakes",
        "stock",
        "chicken stock",
        "vegetable stock",
        "beef stock",
        "stock powder",
        "chicken stock powder",
        "vegetable stock powder",
        "miso paste",
        "green curry paste",
        "red curry paste",
        "curry paste",
        "tomato paste",
        "mayonnaise",
        "mayo",
        "mustard",
        "dijon mustard",
        "worcestershire sauce",
        "hot sauce",
        "sriracha",
        "cornflour",
        "cornstarch",
        "baking powder",
        "baking soda",
        "flour",
        "plain flour",
    }
)

# Phrase hits that usually mean a pantry staple (checked after never-pantry guards).
_PANTRY_PHRASES = (
    "soy sauce",
    "fish sauce",
    "oyster sauce",
    "teriyaki sauce",
    "sweet chilli",
    "sesame oil",
    "olive oil",
    "vegetable oil",
    "rice vinegar",
    "balsamic",
    "garlic powder",
    "onion powder",
    "curry powder",
    "curry paste",
    "miso paste",
    "stock powder",
    "chicken stock",
    "vegetable stock",
    "beef stock",
    "mixed herbs",
    "dried oregano",
    "dried thyme",
    "dried basil",
    "chilli flakes",
    "chili flakes",
    "tomato paste",
    "worcestershire",
)

# Fresh / meal-specific items that must never be treated as pantry staples.
_NEVER_PANTRY = (
    r"\bchicken\b",
    r"\bbeef\b",
    r"\bpork\b",
    r"\blamb\b",
    r"\bsalmon\b",
    r"\bmince\b",
    r"\btofu\b",
    r"\bmilk\b",
    r"\bcream\b",
    r"\byoghurt\b",
    r"\byogurt\b",
    r"\bbutter\b",
    r"\bcheese\b",
    r"\bbread\b",
    r"\bwrap\b",
    r"\btortilla\b",
    r"\bpasta\b",
    r"\brice\b",
    r"\bnoodle",
    r"\bpotato",
    r"\btomato(?!\s+paste)",
    r"\bcarrot",
    r"\bbroccoli",
    r"\bcapsicum",
    r"\bonion(?!\s+powder)",
    r"^garlic$",
    r"\bfresh garlic\b",
    r"\blettuce",
    r"\bspinach",
    r"\bcucumber",
    r"\bavocado",
    r"\begg",
    r"\bcoconut milk\b",
    r"\bbreadcrumb",
)


def normalize_pantry_item(name: str) -> str:
    return name.strip().lower()


def is_never_pantry_ingredient(name: str) -> bool:
    """True for fresh produce / proteins / dairy that must not be pantry-ticked."""
    n = normalize_pantry_item(name)
    if not n:
        return False
    # Allowlisted staples win (chicken stock, garlic powder, onion powder, …)
    if n in _PANTRY_EXACT or any(p in n for p in _PANTRY_PHRASES):
        return False
    if n.endswith(" powder") and any(
        x in n for x in ("garlic", "onion", "chilli", "chili", "curry", "stock")
    ):
        return False
    return any(re.search(pat, n, re.I) for pat in _NEVER_PANTRY)


def looks_like_pantry_staple(name: str) -> bool:
    """True when an ingredient name is a household staple for the recipes checklist."""
    n = normalize_pantry_item(name)
    if not n:
        return False
    # Allowlist first so "chicken stock" / "garlic powder" win over protein/produce guards.
    if n in _PANTRY_EXACT:
        return True
    if any(p in n for p in _PANTRY_PHRASES):
        return True
    if is_never_pantry_ingredient(n):
        return False
    # Generic dried spice / seasoning patterns
    if re.search(
        r"\b(dried|ground)\b.+\b(herb|spice|cumin|paprika|coriander|thyme|oregano)\b",
        n,
    ):
        return True
    if n.endswith(" powder") and any(
        x in n for x in ("garlic", "onion", "chilli", "chili", "curry", "stock")
    ):
        return True
    return False


def apply_pantry_tags(meals: list[Meal]) -> list[Meal]:
    """Tag known staples and clear false pantry flags on fresh/protein items."""
    for meal in meals:
        for ing in meal.ingredients or []:
            if looks_like_pantry_staple(ing.name):
                ing.is_pantry = True
            elif is_never_pantry_ingredient(ing.name):
                ing.is_pantry = False
    return meals


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
