"""Fail-fast when Woolworths catalogue is unavailable — avoid shop-list freezes."""

from __future__ import annotations

import asyncio

import pytest

from shared.models import Ingredient, MealsRequested, UserProfile
from woolworths_adapter.client import WoolworthsError, reset_catalogue_circuit_for_tests
from woolworths_adapter.resolver import ProductResolver


def _profile() -> UserProfile:
    return UserProfile(
        household_size=2,
        days=5,
        dinner_count=5,
        meals_requested=MealsRequested(dinner=5),
        allergies=[],
        mandatory_items=[],
        pantry_items=[],
        likes=[],
        dislikes=[],
        budget_nzd=150,
        simplicity="simple",
        brand_preference="mixed",
        chef_id="basic_sam",
    )


@pytest.fixture(autouse=True)
def _reset_circuit():
    reset_catalogue_circuit_for_tests()
    yield
    reset_catalogue_circuit_for_tests()


@pytest.mark.asyncio
async def test_resolve_ingredient_fails_fast_when_catalogue_errors():
    """Catalogue hard-fails must not burn 100+ search attempts per ingredient."""
    calls = {"n": 0}

    class BoomAdapter:
        async def search(self, query: str, limit: int = 10):
            calls["n"] += 1
            raise WoolworthsError(f"Catalogue blocked for {query!r}")

        async def get_product_match(self, sku: str, *, timeout: float = 12.0):
            return None

        def product_url(self, sku: str, name: str = "") -> str:
            return ""

    resolver = ProductResolver(adapter=BoomAdapter(), offline_mode=False)  # type: ignore[arg-type]
    line = await resolver.resolve_ingredient(
        Ingredient(name="chicken breast", quantity=500, unit="g", for_meals=["Dinner 1"]),
        _profile(),
    )
    assert line is not None
    assert line.sku == "OFFLINE"
    assert calls["n"] <= 8, f"expected fail-fast, got {calls['n']} searches"


@pytest.mark.asyncio
async def test_resolve_batch_trips_circuit_after_first_catalogue_failure():
    """Once catalogue is known-down, later ingredients should not keep hammering it."""
    calls = {"n": 0}

    class BoomAdapter:
        async def search(self, query: str, limit: int = 10):
            calls["n"] += 1
            raise WoolworthsError(f"Catalogue blocked for {query!r}")

        async def get_product_match(self, sku: str, *, timeout: float = 12.0):
            return None

        def product_url(self, sku: str, name: str = "") -> str:
            return ""

    resolver = ProductResolver(adapter=BoomAdapter(), offline_mode=False)  # type: ignore[arg-type]
    profile = _profile()
    first = await resolver.resolve_ingredient(
        Ingredient(name="chicken breast", quantity=500, unit="g", for_meals=["D1"]),
        profile,
    )
    after_first = calls["n"]
    second = await resolver.resolve_ingredient(
        Ingredient(name="broccoli", quantity=1, unit="each", for_meals=["D1"]),
        profile,
    )
    assert first.sku == "OFFLINE"
    assert second.sku == "OFFLINE"
    assert calls["n"] == after_first, (
        f"second ingredient should use open circuit (no new searches); "
        f"first={after_first} total={calls['n']}"
    )
