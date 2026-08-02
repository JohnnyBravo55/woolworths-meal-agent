"""Unit tests for assisted-shop deep links."""

from __future__ import annotations

import pytest

from price_check.links import (
    enrich_line,
    foodstuffs_product_url,
    foodstuffs_search_url,
    freshchoice_search_url,
    store_url_for,
    woolworths_product_url,
    woolworths_search_url,
)
from price_check.models import PriceCheckLine, PriceSource, StoreChain, StoreRef


def test_woolworths_urls():
    assert "stockcode=123" in woolworths_product_url("123")
    assert "searchTerm=milk" in woolworths_search_url("milk")
    store = StoreRef(id="woolworths:online", chain=StoreChain.WOOLWORTHS, name="WW")
    assert store_url_for(store) == "https://www.woolworths.co.nz"


def test_foodstuffs_urls():
    assert foodstuffs_product_url(StoreChain.NEW_WORLD, "501") == (
        "https://www.newworld.co.nz/shop/product/501"
    )
    assert "q=butter" in foodstuffs_search_url(StoreChain.PAKNSAVE, "butter")
    store = StoreRef(id="new_world:abc", chain=StoreChain.NEW_WORLD, name="NW")
    assert store_url_for(store) == "https://www.newworld.co.nz"


def test_freshchoice_search_url():
    url = freshchoice_search_url("freshchoice:barrington", "eggs")
    assert url.startswith("https://barrington.store.freshchoice.co.nz/search?")
    assert "q=eggs" in url


def test_enrich_line_fills_urls():
    store = StoreRef(id="paknsave:1", chain=StoreChain.PAKNSAVE, name="PnS")
    line = PriceCheckLine(
        ingredient="milk",
        quantity=1,
        unit="each",
        product_name="Anchor Milk 2L",
        sku="9001",
        unit_price=4.5,
        line_total=4.5,
        price_source=PriceSource.LIVE,
    )
    enriched = enrich_line(store, line)
    assert enriched.product_url.endswith("/shop/product/9001")
    assert "q=Anchor" in enriched.search_url or "q=Anchor%20Milk" in enriched.search_url


@pytest.mark.asyncio
async def test_engine_estimate_lines_include_search_url():
    from shared.models import GroceryLineItem
    from price_check.engine import basket_for_store

    store = StoreRef(id="freshchoice:barrington", chain=StoreChain.FRESHCHOICE, name="FC")
    items = [
        GroceryLineItem(
            ingredient="eggs",
            sku="OFFLINE",
            product_name="eggs",
            quantity=1,
            unit="Each",
            unit_price=5.0,
            line_total=5.0,
        )
    ]

    async def match_fn(_store, _item):
        return None

    basket = await basket_for_store(store, items, match_fn)
    assert basket.store.store_url.startswith("https://barrington.store.freshchoice.co.nz")
    assert basket.lines[0].search_url.startswith(
        "https://barrington.store.freshchoice.co.nz/search?"
    )
