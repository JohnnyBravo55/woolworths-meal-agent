"""Tests for budget swap suggestion sanity."""

from shared.models import GroceryLineItem, ProductMatch, ResolvedGroceryList, UserProfile, MealsRequested
from agent.budget import BudgetEngine, _valid_swap_savings


def test_savings_cannot_exceed_line_total():
    item = GroceryLineItem(
        ingredient="chicken breast",
        sku="1",
        product_name="Chicken breast",
        quantity=1,
        unit="Each",
        unit_price=8.0,
        line_total=8.0,
    )
    cheaper = ProductMatch(sku="2", product_name="Cheaper chicken", unit_price=2.0, unit="Each")
    assert _valid_swap_savings(item, cheaper) == 6.0
    pricey = ProductMatch(sku="3", product_name="Pricey", unit_price=20.0, unit="Each")
    assert _valid_swap_savings(item, pricey) is None


def test_cross_unit_swap_rejected():
    item = GroceryLineItem(
        ingredient="chicken breast",
        sku="1",
        product_name="Chicken",
        quantity=1,
        unit="Each",
        unit_price=8.0,
        line_total=8.0,
    )
    by_kg = ProductMatch(sku="2", product_name="Chicken kg", unit_price=12.0, unit="Kilogram")
    assert _valid_swap_savings(item, by_kg) is None


def test_suggest_swaps_skips_identical_product_name():
    engine = BudgetEngine()
    resolved = ResolvedGroceryList(
        items=[
            GroceryLineItem(
                ingredient="cheese",
                sku="1",
                product_name="Woolworths Cheese Cheddar Everyday",
                quantity=1,
                unit="Each",
                unit_price=5,
                line_total=5,
            ),
        ],
        total=105,
        budget_nzd=100,
    )
    profile = UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=3),
        budget_nzd=100,
    )

    async def fake_search(query, limit=10):
        return [
            ProductMatch(
                sku="2",
                product_name="Woolworths Cheese Cheddar Everyday",
                unit_price=4,
                unit="Each",
            ),
        ]

    engine.adapter.search = fake_search  # type: ignore[method-assign]
    import asyncio

    suggestions = asyncio.run(engine.suggest_swaps(resolved, profile))
    assert suggestions == []


def test_suggest_swaps_rejects_wrong_oil_type():
    engine = BudgetEngine()
    resolved = ResolvedGroceryList(
        items=[
            GroceryLineItem(
                ingredient="sesame oil",
                sku="1",
                product_name="Woolworths Sesame Oil",
                quantity=1,
                unit="Each",
                unit_price=8,
                line_total=8,
            ),
        ],
        total=150,
        budget_nzd=100,
    )
    profile = UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=3),
        budget_nzd=100,
    )

    async def fake_search(query, limit=10):
        return [
            ProductMatch(
                sku="2",
                product_name="Woolworths Canola Oil",
                unit_price=4,
                unit="Each",
            ),
            ProductMatch(
                sku="3",
                product_name="Woolworths Rice Bran Oil",
                unit_price=3,
                unit="Each",
            ),
        ]

    engine.adapter.search = fake_search  # type: ignore[method-assign]
    import asyncio

    suggestions = asyncio.run(engine.suggest_swaps(resolved, profile))
    assert suggestions == []
