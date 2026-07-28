"""Unit tests for price-check engine (no live HTTP)."""

from __future__ import annotations

import pytest

from shared.models import GroceryLineItem
from price_check.engine import compute_split, run_price_check
from price_check.matching import score_product_name
from price_check.models import PriceCheckLine, PriceSource, StoreChain, StoreRef


def _item(name: str, unit_price: float, qty: float = 1.0) -> GroceryLineItem:
    return GroceryLineItem(
        ingredient=name,
        sku="SKU",
        product_name=name,
        quantity=qty,
        unit="Each",
        unit_price=unit_price,
        line_total=round(unit_price * qty, 2),
    )


def _store(sid: str, chain: StoreChain, name: str) -> StoreRef:
    return StoreRef(id=sid, chain=chain, name=name)


@pytest.mark.asyncio
async def test_estimate_fallback_when_no_live_match():
    items = [_item("milk", 4.5), _item("bread", 3.2)]
    store = _store("woolworths:online", StoreChain.WOOLWORTHS, "WW Online")

    async def match_fn(_store, item):
        return None

    result = await run_price_check(stores=[store], items=items, match_fn=match_fn)
    assert len(result.baskets) == 1
    basket = result.baskets[0]
    assert basket.estimate_count == 2
    assert basket.live_count == 0
    assert basket.total == pytest.approx(7.7)
    assert all(line.price_source == PriceSource.ESTIMATE for line in basket.lines)
    assert "estimate" in basket.lines[0].note.lower()


@pytest.mark.asyncio
async def test_live_prices_and_split_picks_cheapest():
    items = [_item("milk", 5.0), _item("bread", 4.0)]
    ww = _store("woolworths:online", StoreChain.WOOLWORTHS, "WW")
    pns = _store("paknsave:1", StoreChain.PAKNSAVE, "PnS")

    async def match_fn(store, item):
        prices = {
            ("woolworths:online", "milk"): 5.0,
            ("woolworths:online", "bread"): 2.0,
            ("paknsave:1", "milk"): 3.5,
            ("paknsave:1", "bread"): 3.0,
        }
        unit = prices[(store.id, item.ingredient)]
        return PriceCheckLine(
            ingredient=item.ingredient,
            quantity=1,
            unit="each",
            product_name=item.ingredient,
            sku="X",
            unit_price=unit,
            line_total=unit,
            price_source=PriceSource.LIVE,
        )

    result = await run_price_check(
        stores=[ww, pns], items=items, match_fn=match_fn, include_split=True
    )
    assert result.baskets[0].total == pytest.approx(6.5)  # PnS cheaper total
    assert result.split is not None
    # milk@PnS 3.5 + bread@WW 2.0 = 5.5
    assert result.split.total == pytest.approx(5.5)
    assert result.split.savings_vs_cheapest_single_store == pytest.approx(1.0)
    by_ing = {a.ingredient: a.store_id for a in result.split.assignments}
    assert by_ing["milk"] == "paknsave:1"
    assert by_ing["bread"] == "woolworths:online"


def test_compute_split_none_for_single_store():
    assert compute_split([]) is None


def test_score_product_name_rejects_unrelated():
    assert score_product_name("milk", "chicken thighs") == 0.0
    assert score_product_name("milk", "Standard Milk") > 0
