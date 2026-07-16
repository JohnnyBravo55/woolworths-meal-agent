"""Allergy-aware ingredient and product validation."""

from __future__ import annotations

from shared.gluten_label import GlutenLabelAssessment, GlutenLabelStatus, assess_gluten_label
from shared.models import UserProfile

_GLUTEN_PRODUCT_TERMS = frozenset(
    {
        "wheat",
        "barley",
        "rye",
        "malt",
        "semolina",
        "spelt",
        "bulgur",
        "couscous",
        "seitan",
        "bread",
        "bun",
        "roll",
        "muffin",
        "cake",
        "pastry",
        "croissant",
        "crumpet",
        "bagel",
        "pita",
        "wrap",
        "tortilla",
        "pasta",
        "noodle",
        "lasagne",
        "pizza",
        "flour",
        "breadcrumb",
        "breadcrumbs",
        "crumbed",
        "crumbing",
        "breaded",
        "batter",
        "panko",
        "tempura",
        "schnitzel",
        "stuffing",
        "dumpling",
        "wonton",
        "spring roll",
        "crouton",
        "fish finger",
        "fish fingers",
        "biscuit",
        "cookie",
        "cracker",
        "cereal",
        "muesli",
        "granola",
        "soy sauce",
    }
)

_GLUTEN_FREE_MARKERS = frozenset(
    {
        "gluten free",
        "gluten-free",
        "free from gluten",
        "gf ",
        " gf",
        "no gluten",
        "tamari",
    }
)

_GLUTEN_INGREDIENT_TERMS = frozenset(
    {
        "bread",
        "pasta",
        "noodle",
        "wrap",
        "tortilla",
        "taco shell",
        "taco shells",
        "flour",
        "pita",
        "bagel",
        "muffin",
        "cake",
        "crumpet",
        "soy sauce",
        "breadcrumbs",
        "cereal",
        "muesli",
        "granola",
        "pizza",
        "lasagne",
        "couscous",
        "seitan",
        "banana bread",
    }
)


def profile_has_gluten_allergy(profile: UserProfile) -> bool:
    return any("gluten" in a for a in profile.allergies)


def _is_gluten_free_label(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in _GLUTEN_FREE_MARKERS)


def ingredient_is_gluten_risk(name: str) -> bool:
    lower = name.lower()
    if _is_gluten_free_label(lower):
        return False
    if any(term in lower for term in _GLUTEN_INGREDIENT_TERMS):
        return True
    return "bread" in lower


def product_contains_gluten(product_name: str, brand: str = "") -> bool:
    combined = f"{product_name} {brand}".lower()
    if _is_gluten_free_label(combined):
        return False
    if "rice cracker" in combined or "rice crackers" in combined or "rice cake" in combined:
        return False
    if any(term in combined for term in _GLUTEN_PRODUCT_TERMS):
        return True
    # Coating/crumbs often omitted from ingredient lists on search results
    if " crumb" in combined or combined.startswith("crumb"):
        return True
    return False


def is_product_safe_for_profile(
    product_name: str,
    brand: str,
    profile: UserProfile,
    *,
    ingredient_name: str = "",
    label_assessment: GlutenLabelAssessment | None = None,
) -> bool:
    if profile_has_gluten_allergy(profile):
        if label_assessment is not None:
            if label_assessment.status == GlutenLabelStatus.CONTAINS:
                return False
        if product_contains_gluten(product_name, brand):
            return False
        ing = ingredient_name.lower()
        if "bread" in ing and not _is_gluten_free_label(f"{product_name} {brand}"):
            return False
        # Plain fish/meat recipes must not resolve to crumbed/breaded products
        wants_coating = any(
            x in ing for x in ("crumbed", "breaded", "battered", "schnitzel", "tempura", "panko")
        )
        if ing and not wants_coating:
            combined = f"{product_name} {brand}".lower()
            if any(
                x in combined
                for x in ("crumbed", "breaded", "tempura", "panko", "fish finger", "schnitzel")
            ):
                return False
    return True


def ingredient_conflicts_allergies(name: str, profile: UserProfile) -> bool:
    if not profile.allergies:
        return False
    lower = name.lower()
    if _is_gluten_free_label(lower):
        return False
    for allergen in profile.allergies:
        if allergen in lower:
            return True
    if profile_has_gluten_allergy(profile) and ingredient_is_gluten_risk(name):
        return True
    return False


def normalize_mandatory_for_allergies(
    items: list[str],
    profile: UserProfile | None = None,
    *,
    allergies: list[str] | None = None,
) -> list[str]:
    allergy_list = profile.allergies if profile else (allergies or [])
    if not any("gluten" in a for a in allergy_list):
        return items
    out: list[str] = []
    for item in items:
        lower = item.lower()
        if lower == "bread" or (lower.endswith(" bread") and "gluten" not in lower):
            out.append("gluten free bread")
        else:
            out.append(item)
    return out
