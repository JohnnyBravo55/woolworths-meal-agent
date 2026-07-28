"""Simple product name matching for price-check adapters."""

from __future__ import annotations

import re


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1}


def score_product_name(ingredient: str, product_name: str, brand: str = "") -> float:
    """Higher is better. 0 means reject."""
    ing = ingredient.lower().strip()
    prod = f"{brand} {product_name}".lower().strip()
    if not ing or not product_name.strip():
        return 0.0
    if ing == product_name.lower().strip():
        return 100.0
    if ing in prod:
        return 80.0 + min(10.0, len(ing))
    ing_tokens = _tokens(ing)
    prod_tokens = _tokens(prod)
    if not ing_tokens:
        return 0.0
    overlap = ing_tokens & prod_tokens
    if not overlap:
        return 0.0
    # Reject obvious wrong categories for common proteins/dairy keywords when no overlap ratio
    ratio = len(overlap) / len(ing_tokens)
    if ratio < 0.5:
        return 0.0
    return 40.0 + 40.0 * ratio


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
