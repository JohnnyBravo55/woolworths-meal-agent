"""Tests for pre-cart validation."""

import pytest

from shared.models import GroceryLineItem, MealsRequested, UserProfile
from woolworths_adapter.cart_validation import validate_product_for_ingredient
from woolworths_adapter.search_helpers import is_plausible_match


def test_apples_reject_baby_puree():
    assert is_plausible_match("apples", "woolworths fruit puree apples") is False
    v = validate_product_for_ingredient("apples", "woolworths fruit puree apples")
    assert v.blocked is True


def test_apples_accept_fresh():
    assert is_plausible_match("apples", "fresh fruit apples royal gala") is True
    v = validate_product_for_ingredient("apples", "fresh fruit apples royal gala")
    assert v.blocked is False


def test_oats_reject_baby_food():
    assert is_plausible_match(
        "oats", "only organic baby food apple & banana with oats"
    ) is False


def test_baby_food_brand_blocked():
    v = validate_product_for_ingredient(
        "bananas", "woolworths smiling tums baby food pear, banana & mango"
    )
    assert v.blocked is True


def test_face_mask_blocked_for_cucumber():
    v = validate_product_for_ingredient(
        "cucumber", "glow lab hydrating glow mask aloe vera & cucumber"
    )
    assert v.blocked is True


def test_capsicum_hummus_blocked():
    v = validate_product_for_ingredient("capsicum", "lisas hummus chargrilled capsicum")
    assert v.blocked is True


def test_cucumber_drink_mixer_blocked():
    v = validate_product_for_ingredient(
        "cucumber", "barker's drink mixers lemon lime cucumber & mint"
    )
    assert v.blocked is True


def test_carrots_petite_baby_ok():
    assert is_plausible_match("carrots", "fresh vegetable carrots petite baby") is True
    v = validate_product_for_ingredient("carrots", "fresh vegetable carrots petite baby")
    assert v.blocked is False


@pytest.mark.asyncio
async def test_audit_blocks_bad_line():
    from woolworths_adapter.cart_validation import audit_resolved_list

    profile = UserProfile(household_size=2, meals_requested=MealsRequested(dinner=5), budget_nzd=200)
    items = [
        GroceryLineItem(
            ingredient="apples",
            sku="123",
            product_name="woolworths fruit puree apples",
            quantity=1,
            unit="Each",
            unit_price=2,
            line_total=2,
            in_stock=True,
        )
    ]
    out = await audit_resolved_list(items, profile, adapter=None, meal_plan=None)
    assert out[0].cart_blocked is True
    assert out[0].block_reason
