"""Tests for cart quantity normalization."""

from shared.models import Ingredient, ProductMatch, UserProfile, MealsRequested
from woolworths_adapter.quantities import normalize_cart_quantity


def _product(unit: str = "Each", price: float = 10.0) -> ProductMatch:
    return ProductMatch(
        sku="123",
        product_name="Test Product",
        unit_price=price,
        unit=unit,  # type: ignore[arg-type]
    )


def test_500g_becomes_one_pack_not_500_each():
    ing = Ingredient(name="chicken breast", quantity=500, unit="g")
    qty, unit = normalize_cart_quantity(ing, _product("Each"))
    assert qty == 1.0
    assert unit == "Each"


def test_500_grams_unit():
    ing = Ingredient(name="chicken breast", quantity=500, unit="grams")
    qty, unit = normalize_cart_quantity(ing, _product("Each"))
    assert qty == 1.0
    assert unit == "Each"


def test_llm_mistake_500_each_treated_as_grams():
    """500 each is almost certainly 500g mislabeled by the LLM."""
    ing = Ingredient(name="chicken breast", quantity=500, unit="each")
    qty, unit = normalize_cart_quantity(ing, _product("Each"))
    assert qty == 1.0
    assert unit == "Each"


def test_kg_product_gets_kg_quantity():
    ing = Ingredient(name="potatoes", quantity=800, unit="g")
    qty, unit = normalize_cart_quantity(ing, _product("Kilogram"))
    assert unit == "Kilogram"
    assert qty == 0.8


def test_fillets_capped():
    ing = Ingredient(name="salmon fillets", quantity=4, unit="each")
    qty, unit = normalize_cart_quantity(ing, _product("Each"), household_size=2)
    assert qty == 4.0
    assert unit == "Each"


def test_deduped_weight_sums_safely():
    ing = Ingredient(name="chicken breast", quantity=2500, unit="g")
    qty, unit = normalize_cart_quantity(ing, _product("Kilogram"))
    assert unit == "Kilogram"
    assert qty <= 5.0
