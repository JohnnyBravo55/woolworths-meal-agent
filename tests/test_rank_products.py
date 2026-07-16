"""Rank products prefers in-stock but falls back to out-of-stock."""

from shared.models import BrandPreference, ProductMatch
from woolworths_adapter.resolver import rank_products


def test_rank_falls_back_to_out_of_stock_when_none_in_stock():
    matches = [
        ProductMatch(
            sku="290252",
            product_name="woolworths nz salmon fillets hamana skin on",
            unit_price=18.0,
            in_stock=False,
        )
    ]
    ranked = rank_products(matches, BrandPreference.MIXED, "salmon fillets")
    assert len(ranked) == 1
    assert ranked[0].sku == "290252"


def test_rank_prefers_in_stock():
    matches = [
        ProductMatch(
            sku="1",
            product_name="woolworths nz salmon fillets hamana skin on",
            unit_price=20.0,
            in_stock=False,
        ),
        ProductMatch(
            sku="2",
            product_name="woolworths salmon fillets skin on and bone in",
            unit_price=22.0,
            in_stock=True,
        ),
    ]
    ranked = rank_products(matches, BrandPreference.MIXED, "salmon fillets")
    assert ranked[0].sku == "2"
