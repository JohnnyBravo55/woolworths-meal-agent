"""Integration smoke tests for Woolworths adapter (session-dependent)."""

import os

import pytest

from woolworths_adapter.client import WoolworthsAdapter
from woolworths_adapter.resolver import ProductResolver, rank_products
from shared.models import BrandPreference, ProductMatch, UserProfile, MealsRequested


pytestmark = pytest.mark.integration


def _has_woolies_session() -> bool:
    try:
        from woolies_cli.paths import cookies_file

        return cookies_file().exists()
    except Exception:
        return False


skip_no_session = pytest.mark.skipif(
    not _has_woolies_session(),
    reason="No Woolworths session — run 'woolies login' first",
)


@skip_no_session
@pytest.mark.asyncio
async def test_search_milk():
    adapter = WoolworthsAdapter()
    results = await adapter.search("milk", limit=3)
    assert len(results) >= 1
    assert results[0].sku
    assert results[0].product_name


@skip_no_session
@pytest.mark.asyncio
async def test_session_available():
    adapter = WoolworthsAdapter()
    assert await adapter.is_session_available() is True


@skip_no_session
@pytest.mark.asyncio
async def test_resolve_ingredient():
    adapter = WoolworthsAdapter()
    resolver = ProductResolver(adapter)
    profile = UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=1),
        budget_nzd=50,
    )
    from shared.models import Ingredient

    line = await resolver.resolve_ingredient(
        Ingredient(name="bread", quantity=1, unit="loaf"),
        profile,
    )
    assert line is not None
    assert line.sku
    assert line.line_total > 0


def test_rank_products_prefers_budget_brands():
    matches = [
        ProductMatch(
            sku="1",
            product_name="Organic Free Range Chicken",
            brand="Premium",
            unit_price=15.0,
            in_stock=True,
        ),
        ProductMatch(
            sku="2",
            product_name="Pams Chicken Breast",
            brand="Pams",
            unit_price=10.0,
            in_stock=True,
        ),
    ]
    ranked = rank_products(matches, BrandPreference.BUDGET)
    assert ranked[0].sku == "2"


@pytest.mark.asyncio
async def test_orchestrator_demo_pipeline_offline():
    """Demo pipeline works without Woolworths session (export-only)."""
    from agent.conversation import ConversationManager
    from agent.orchestrator import MealAgentOrchestrator

    orchestrator = MealAgentOrchestrator()
    profile = ConversationManager.sample_profile()
    state = await orchestrator.run_full_pipeline(
        profile,
        auto_approve=True,
        export_only=True,
        auto_swap=False,
        offline=True,
    )
    assert state.meal_plan is not None
    assert len(state.meal_plan.meals) > 0
    assert state.resolved_list is not None
    assert len(state.resolved_list.items) > 0
