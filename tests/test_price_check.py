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
async def test_zero_live_store_is_skipped_not_compared():
    items = [_item("milk", 4.5), _item("bread", 3.2)]
    store = _store("woolworths:online", StoreChain.WOOLWORTHS, "WW Online")
    pns = _store("paknsave:1", StoreChain.PAKNSAVE, "PnS")

    async def match_fn(store, item):
        if store.id.startswith("woolworths"):
            return None
        return PriceCheckLine(
            ingredient=item.ingredient,
            quantity=1,
            unit="each",
            product_name=item.ingredient,
            sku="X",
            unit_price=float(item.unit_price),
            line_total=float(item.line_total),
            price_source=PriceSource.LIVE,
        )

    result = await run_price_check(stores=[store, pns], items=items, match_fn=match_fn)
    assert len(result.baskets) == 1
    assert result.baskets[0].store.id == "paknsave:1"
    assert len(result.skipped) == 1
    assert result.skipped[0].store.id == "woolworths:online"
    assert "not included" in result.skipped[0].reason.lower()


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


def test_score_product_name_rejects_avocado_salad_kit():
    assert score_product_name("avocado", "Taylor Farms Avocado Ranch Chopped Kit 350g") == 0.0
    assert score_product_name("avocado", "Fresh Avocado Pre-Ripened") > 50


def test_score_product_name_rejects_coconut_milk_for_milk():
    assert score_product_name("milk", "Coconut Milk 400ml") == 0.0
    assert score_product_name("milk", "Anchor Blue Milk 2L") > 50


def test_score_product_name_rejects_broccoli_cheese_bites():
    assert score_product_name("broccoli head", "Leader Vegatarian Broccoli & Cheese Bites 500g") == 0.0
    assert score_product_name("broccoli head", "Fresh Broccoli Head") > 50


def test_score_product_name_rejects_pork_blend_for_beef_mince():
    assert score_product_name("beef mince", "Woolworths Pork & Beef Mince 300g") == 0.0
    assert score_product_name("beef mince", "NZ Premium Beef Mince kg") > 50


def test_score_product_name_accepts_courgette_for_zucchini():
    assert score_product_name("zucchini", "Imported Courgettes") > 50
    assert score_product_name("zucchini", "Organic Pumpkin Kumara & Courgette With Quinoa 6+ Months Pureed") == 0.0


def test_score_product_name_allows_salad_when_ingredient_is_salad_greens():
    assert score_product_name("mixed salad greens", "Mixed Leaf Salad") > 50
    assert score_product_name("mixed salad greens", "Mesclun Salad") > 50
    assert score_product_name("mixed salad greens", "Crispy Salad With Kiwi Dressing") == 0.0


def test_search_query_variants_include_produce_aliases():
    from price_check.matching import search_query_variants

    broccoli = search_query_variants("broccoli head")
    assert "broccoli" in [q.lower() for q in broccoli]
    zucchini = search_query_variants("zucchini")
    assert any("courgette" in q.lower() for q in zucchini)


def test_score_product_name_accepts_egg_noodles():
    assert score_product_name("egg noodles", "High Mark Egg Noodles Round") > 50
    assert score_product_name("egg", "Egg Noodles Round") == 0.0


def test_score_product_name_rejects_snap_pea_snacks_and_mixes():
    assert score_product_name("snap peas", "Harvest Snaps Original Salted Baked Pea Crisps") == 0.0
    assert score_product_name("snap peas", "Steam Fresh Green Beans Broccoli & Sugarsnap Peas Vege Mix") == 0.0
    assert score_product_name("snap peas", "Sugar Snap Peas") > 50


def test_score_product_name_rejects_honey_nuts_and_cheese_roll():
    assert score_product_name("honey", "Cashews Honey Roasted") == 0.0
    assert score_product_name("honey", "Airborne Multifloral Honey 500g") > 50
    assert score_product_name("cheese", "Cheese Roll") == 0.0
    assert score_product_name("salsa", "Sunbites Grainwaves Salsa 140g") == 0.0


def test_freshchoice_parse_products_from_search_html():
    from price_check.freshchoice import _parse_products

    sample = """
    <div class="talker__name talker__section" title="WW Milk Standard 2L">
    <span class="talker__product-name">WW Milk Standard</span>
    <span class="weak size talker__name__size">2L</span>
    </div>
    <strong class="price__sell" title="">$5.09</strong>
    <form class="item-quantity-form" id="new_order_line_for_5817d6c6e1272f60920070d5">
    <div class="talker__name talker__section" title="Whittaker&#39;s Chocolate Block Creamy Milk 250g">
    <span class="talker__product-name">Whittaker&#39;s Chocolate Block Creamy Milk</span>
    <span class="weak size talker__name__size">250g</span>
    </div>
    <strong class="price__sell" title="">$7.49</strong>
    <form id="new_order_line_for_5817d9aee1272f60920204e0">
    """
    products = _parse_products(sample)
    assert len(products) >= 2
    milk = next(p for p in products if "Milk Standard" in p["name"])
    assert milk["unit_price"] == 5.09
    assert milk["size"] == "2L"
    assert milk["sku"] == "5817d6c6e1272f60920070d5"
    choc = next(p for p in products if "Whittaker" in p["name"])
    assert "Creamy Milk" in choc["name"]
    assert choc["unit_price"] == 7.49


@pytest.mark.asyncio
async def test_christchurch_central_search_finds_nearby_chains():
    from price_check.directory import search_stores

    stores = await search_stores("Christchurch Central", limit=20)
    chains = {s.chain.value for s in stores}
    assert "woolworths" in chains
    assert "new_world" in chains
    assert "paknsave" in chains
    assert any("durham" in s.name.lower() for s in stores)
    assert any("moorhouse" in s.name.lower() for s in stores)


@pytest.mark.asyncio
async def test_woolworths_suburb_search_finds_ferrymead():
    from price_check.directory import search_stores
    from price_check.models import StoreChain

    stores = await search_stores("Ferrymead", StoreChain.WOOLWORTHS, limit=10)
    assert stores
    assert any("ferrymead" in s.name.lower() or "ferrymead" in s.suburb.lower() for s in stores)


@pytest.mark.asyncio
async def test_woolworths_unknown_suburb_does_not_invent_store():
    from price_check.directory import search_stores
    from price_check.models import StoreChain

    stores = await search_stores("Someobscureville", StoreChain.WOOLWORTHS, limit=5)
    assert stores == []
    assert not any(s.id.startswith("woolworths:local:") for s in stores)


@pytest.mark.asyncio
async def test_woolworths_circuit_opens_after_hard_block(monkeypatch):
    import httpx

    from price_check import woolworths_public as ww

    ww.reset_circuit_for_tests()

    class FakeResp:
        status_code = 403
        text = "blocked"
        request = httpx.Request("GET", "https://www.woolworths.co.nz/api/v1/products")

        def raise_for_status(self):
            raise httpx.HTTPStatusError("403", request=self.request, response=self)

        def json(self):
            return {}

    class FakeClient:
        is_closed = False

        async def get(self, *args, **kwargs):
            return FakeResp()

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(ww, "_get_client", fake_get_client)
    with pytest.raises(ww.WoolworthsCatalogueUnavailable):
        await ww.search_products("milk")
    with pytest.raises(ww.WoolworthsCatalogueUnavailable):
        await ww.search_products("bread")
    ww.reset_circuit_for_tests()

