"""Tests for cart SKU merging."""

from shared.models import GroceryLineItem

from woolworths_adapter.cart_merge import merge_line_items_by_sku


def _line(sku: str, ingredient: str, qty: float = 1.0) -> GroceryLineItem:
    return GroceryLineItem(
        ingredient=ingredient,
        sku=sku,
        product_name=f"product {sku}",
        quantity=qty,
        unit="Each",
        unit_price=2.0,
        line_total=2.0 * qty,
        for_meals=[ingredient],
    )


def test_merge_duplicate_skus():
    items = [_line("123", "rice"), _line("123", "sushi rice")]
    merged, dupes = merge_line_items_by_sku(items)
    assert dupes == 1
    assert len(merged) == 1
    assert merged[0].quantity == 2.0
    assert "rice" in merged[0].ingredient and "sushi rice" in merged[0].ingredient
