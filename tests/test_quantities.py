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


def test_fillets_capped_to_one_per_person():
    ing = Ingredient(name="salmon fillets", quantity=4, unit="each")
    qty, unit = normalize_cart_quantity(ing, _product("Each"), household_size=2)
    assert qty == 2.0
    assert unit == "Each"


def test_salmon_kg_capped_for_two_people():
    ing = Ingredient(name="salmon fillets", quantity=1000, unit="g")
    qty, unit = normalize_cart_quantity(ing, _product("Kilogram"), household_size=2)
    assert unit == "Kilogram"
    assert qty <= 0.36


def test_deduped_weight_sums_safely():
    ing = Ingredient(name="chicken breast", quantity=2500, unit="g")
    qty, unit = normalize_cart_quantity(ing, _product("Kilogram"))
    assert unit == "Kilogram"
    assert qty <= 5.0


def test_four_tomatoes_buys_one_bag_not_four():
    """Recipe '4 tomatoes' must not become 4× 600g tomato bags."""
    ing = Ingredient(name="tomatoes", quantity=4, unit="each")
    bag = ProductMatch(
        sku="339889",
        product_name="woolworths fresh tomatoes",
        size="600g",
        unit_price=8.0,
        unit="Each",
    )
    qty, unit = normalize_cart_quantity(ing, bag, household_size=2)
    assert unit == "Each"
    assert qty == 1.0


def test_four_tomatoes_loose_buys_by_weight():
    ing = Ingredient(name="tomatoes", quantity=4, unit="each")
    loose = ProductMatch(
        sku="149681",
        product_name="fresh tomatoes loose",
        size="per kg",
        unit_price=10.95,
        unit="Kilogram",
    )
    qty, unit = normalize_cart_quantity(ing, loose, household_size=2)
    assert unit == "Kilogram"
    assert 0.35 <= qty <= 0.7


def test_four_carrots_buys_one_bag_not_four():
    ing = Ingredient(name="carrots", quantity=4, unit="each")
    bag = ProductMatch(
        sku="283277",
        product_name="woolworths fresh vegetable carrots",
        size="1.5kg",
        unit_price=3.5,
        unit="Each",
    )
    qty, unit = normalize_cart_quantity(ing, bag, household_size=2)
    assert unit == "Each"
    assert qty == 1.0


def test_carrot_bag_uses_weight_when_many_pieces_needed():
    """Many carrots can require more than one bag if pack is small."""
    ing = Ingredient(name="carrots", quantity=20, unit="each")
    bag = ProductMatch(
        sku="x",
        product_name="fresh vegetable carrots bag",
        size="500g",
        unit_price=2.0,
        unit="Each",
    )
    qty, unit = normalize_cart_quantity(ing, bag, household_size=4)
    assert unit == "Each"
    assert qty >= 2.0
