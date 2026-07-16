"""Tests for Woolworths adapter product parsing."""

from woolworths_adapter.client import WoolworthsAdapter


def test_to_match_handles_null_size():
    match = WoolworthsAdapter._to_match(
        {
            "sku": "123",
            "name": "woolworths fresh broccoli",
            "brand": "woolworths",
            "size": None,
            "price": 3.5,
            "unit": "Each",
            "in_stock": True,
        }
    )
    assert match.size == ""
    assert match.product_name == "woolworths fresh broccoli"
