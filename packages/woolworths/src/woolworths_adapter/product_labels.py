"""Fetch and parse Woolworths NZ product label data (ingredients, allergens)."""

from __future__ import annotations

from typing import Any

from shared.gluten_label import ProductLabelInfo, strip_label_html


def parse_product_label(raw: dict[str, Any]) -> ProductLabelInfo:
    ingredients_block = raw.get("ingredients") or {}
    ingredient_lines = ingredients_block.get("ingredients") or []
    if not isinstance(ingredient_lines, list):
        ingredient_lines = [str(ingredient_lines)]

    allergens = raw.get("allergens") or []
    if not isinstance(allergens, list):
        allergens = [str(allergens)]

    claims = raw.get("claims") or []
    if not isinstance(claims, list):
        claims = [str(claims)]

    maybe = raw.get("allergenMaybePresent")
    if maybe is not None:
        maybe = strip_label_html(str(maybe))

    return ProductLabelInfo(
        ingredients=[strip_label_html(str(x)) for x in ingredient_lines if str(x).strip()],
        allergens=[strip_label_html(str(x)) for x in allergens if str(x).strip()],
        allergen_maybe_present=maybe,
        claims=[strip_label_html(str(x)) for x in claims if str(x).strip()],
    )
