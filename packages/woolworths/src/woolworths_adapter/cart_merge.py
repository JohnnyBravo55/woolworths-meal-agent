"""Merge shopping lines that resolve to the same Woolworths SKU."""

from __future__ import annotations

from shared.models import GroceryLineItem

from woolworths_adapter.quantities import MAX_EACH_QUANTITY, MAX_KG_QUANTITY


def merge_line_items_by_sku(items: list[GroceryLineItem]) -> tuple[list[GroceryLineItem], int]:
    """
    Collapse duplicate SKUs so cart adds match unique trolley lines.

    Returns merged items and how many extra list rows were folded in.
    """
    merged: dict[str, GroceryLineItem] = {}
    duplicate_rows = 0

    for item in items:
        if item.sku == "OFFLINE":
            # Offline rows are ingredient-specific — keep separate
            key = f"offline:{item.ingredient.lower()}"
            if key not in merged:
                merged[key] = item.model_copy(deep=True)
            else:
                duplicate_rows += 1
                existing = merged[key]
                existing.quantity = max(existing.quantity, item.quantity)
                existing.line_total = round(existing.unit_price * existing.quantity, 2)
                for meal in item.for_meals:
                    if meal not in existing.for_meals:
                        existing.for_meals.append(meal)
            continue

        if item.sku not in merged:
            merged[item.sku] = item.model_copy(deep=True)
            continue

        duplicate_rows += 1
        existing = merged[item.sku]
        if item.unit == existing.unit:
            existing.quantity = min(
                existing.quantity + item.quantity,
                MAX_KG_QUANTITY if item.unit == "Kilogram" else MAX_EACH_QUANTITY,
            )
        else:
            existing.quantity = max(existing.quantity, item.quantity)
            existing.unit = item.unit
        existing.line_total = round(existing.unit_price * existing.quantity, 2)
        for meal in item.for_meals:
            if meal not in existing.for_meals:
                existing.for_meals.append(meal)
        if item.ingredient.lower() not in existing.ingredient.lower():
            existing.ingredient = f"{existing.ingredient} / {item.ingredient}"

    return list(merged.values()), duplicate_rows
