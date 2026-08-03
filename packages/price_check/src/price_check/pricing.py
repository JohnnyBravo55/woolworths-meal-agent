"""Convert shop-list amounts into sane purchase qty/totals for price check."""

from __future__ import annotations

import re
from typing import Any, Literal

# Typical edible weight when a recipe says "N fillets/pieces".
_PROTEIN_EACH_KG: dict[str, float] = {
    "salmon": 0.18,
    "fish": 0.18,
    "chicken": 0.18,
    "beef": 0.2,
    "lamb": 0.2,
    "pork": 0.18,
    "tofu": 0.25,
}

# Hard caps so one line cannot imply a catering order.
_MAX_PROTEIN_KG = 1.5
_MAX_SALMON_KG = 1.0
_MAX_PACKS = 3


def _norm_unit(unit: str) -> str:
    return (unit or "").lower().strip().replace(".", "")


def parse_pack_kg(display: str, name: str = "") -> float | None:
    """Parse pack weight from catalogue size text like '2kg', '450g'."""
    blob = f"{display} {name}".lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", blob)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*g\b", blob)
    if m:
        grams = float(m.group(1))
        if grams >= 50:
            return grams / 1000.0
    return None


def is_weight_priced(sale_type: str | None, sku: str = "", display: str = "") -> bool:
    if (sale_type or "").upper() == "WEIGHT":
        return True
    sku_u = (sku or "").upper()
    if "-KGM-" in sku_u or sku_u.endswith("-KGM") or sku_u.endswith("KGM"):
        return True
    return (display or "").strip().lower() in {"kg", "kilogram", "kilograms"}


def needed_kg(ingredient: str, quantity: float, unit: str) -> float:
    """Estimate kilograms needed for a shop-list protein/produce line."""
    qty = float(quantity or 1) or 1.0
    u = _norm_unit(unit)
    name = ingredient.lower()

    if u in {"kg", "kilogram", "kilograms", "kilo"}:
        kg = qty
    elif u in {"g", "gram", "grams"}:
        kg = qty / 1000.0
    elif qty >= 50 and u in {"each", "piece", "pieces", "fillet", "fillets", ""}:
        # LLM-style grams mislabeled as each
        kg = qty / 1000.0
    else:
        # Count units (fillets / thighs): convert via typical piece weight
        each_kg = 0.2
        for key, val in _PROTEIN_EACH_KG.items():
            if key in name:
                each_kg = val
                break
        kg = max(1.0, qty) * each_kg

    cap = _MAX_SALMON_KG if "salmon" in name else _MAX_PROTEIN_KG
    if any(p in name for p in _PROTEIN_EACH_KG):
        kg = min(kg, cap)
    else:
        kg = min(kg, 5.0)
    return max(0.15, round(kg, 2))


def price_purchase(
    *,
    ingredient: str,
    quantity: float,
    unit: str,
    unit_price: float,
    sale_type: str | None = None,
    sku: str = "",
    display: str = "",
    product_name: str = "",
) -> tuple[float, str, float]:
    """
    Return (buy_qty, buy_unit, line_total) for a matched catalogue product.

    Prevents `4 each fillets × $55/kg` from becoming a $220 line.
    """
    if unit_price <= 0:
        return 1.0, "each", 0.0

    weight_priced = is_weight_priced(sale_type, sku=sku, display=display)
    if weight_priced:
        kg = needed_kg(ingredient, quantity, unit)
        return kg, "kg", round(unit_price * kg, 2)

    pack_kg = parse_pack_kg(display, product_name)
    if pack_kg and any(p in ingredient.lower() for p in _PROTEIN_EACH_KG):
        need = needed_kg(ingredient, quantity, unit)
        packs = int(max(1, -(-int(need * 1000) // int(pack_kg * 1000))))  # ceil
        packs = min(packs, _MAX_PACKS)
        return float(packs), "each", round(unit_price * packs, 2)

    # Generic pack / each product — buy one unless shop list already asks for packs
    u = _norm_unit(unit)
    if u in {"each", "pack", "packs", "piece", "pieces", "fillet", "fillets"} and quantity <= 12:
        # For proteins against a pack SKU, one pack usually covers the meal set
        if any(p in ingredient.lower() for p in _PROTEIN_EACH_KG):
            return 1.0, "each", round(unit_price, 2)
        qty = max(1.0, min(float(quantity), 6.0))
        return qty, "each", round(unit_price * qty, 2)

    return 1.0, "each", round(unit_price, 2)


def pick_best_priced_product(
    ingredient: str,
    candidates: list[dict[str, Any]],
    *,
    quantity: float,
    unit: str,
    score_fn,
) -> dict[str, Any] | None:
    """Prefer matches that cover the need at the lowest estimated line total."""
    scored: list[tuple[float, float, dict[str, Any]]] = []
    for cand in candidates:
        name = str(cand.get("name") or "")
        brand = str(cand.get("brand") or "")
        score = float(score_fn(ingredient, name, brand))
        if score <= 0:
            continue
        unit_price = float(cand.get("unit_price") or 0)
        if unit_price <= 0 and cand.get("price_cents") is not None:
            try:
                unit_price = int(cand["price_cents"]) / 100.0
            except (TypeError, ValueError):
                unit_price = 0.0
        if unit_price <= 0:
            continue
        _, _, total = price_purchase(
            ingredient=ingredient,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            sale_type=str(cand.get("saleType") or cand.get("sale_type") or ""),
            sku=str(cand.get("sku") or ""),
            display=str(cand.get("display") or cand.get("size") or ""),
            product_name=name,
        )
        # Prefer packs slightly when totals are close — more realistic shop
        pack_bonus = 0.0
        if not is_weight_priced(
            str(cand.get("saleType") or ""),
            sku=str(cand.get("sku") or ""),
            display=str(cand.get("display") or ""),
        ):
            pack_bonus = 0.5
        scored.append((total - pack_bonus, -score, cand))
    if not scored:
        return None
    scored.sort(key=lambda row: (row[0], row[1]))
    return scored[0][2]
