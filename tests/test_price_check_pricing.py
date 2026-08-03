"""Tests for price-check purchase quantity math."""

from price_check.matching import score_product_name
from price_check.pricing import is_weight_priced, needed_kg, price_purchase


def test_fillets_each_not_multiplied_as_kg():
    qty, unit, total = price_purchase(
        ingredient="salmon fillets",
        quantity=4,
        unit="each",
        unit_price=54.99,
        sale_type="WEIGHT",
        sku="5134102-KGM-000",
        display="kg",
        household_size=2,
    )
    assert unit == "kg"
    assert qty <= 0.4  # ~2 fillets for 2 people
    assert total < 25  # was wrongly ~$220


def test_chicken_thighs_four_each_against_per_kg():
    qty, unit, total = price_purchase(
        ingredient="chicken thighs",
        quantity=4,
        unit="Each",
        unit_price=26.29,
        sale_type="WEIGHT",
        sku="5268350-KGM-000",
        display="kg",
        household_size=2,
    )
    assert unit == "kg"
    assert total < 20  # was wrongly ~$105


def test_two_kg_salmon_capped_for_two_people():
    assert needed_kg("salmon fillets", 2, "kg", household_size=2) <= 0.4


def test_prefers_family_pack_math():
    qty, unit, total = price_purchase(
        ingredient="chicken thighs",
        quantity=4,
        unit="each",
        unit_price=16.99,
        sale_type="UNITS",
        sku="5006198-EA-000",
        display="2kg",
        product_name="Pams Tender Basted Chicken Thighs",
    )
    assert unit == "each"
    assert qty == 1.0
    assert total == 16.99


def test_salmon_does_not_match_mackerel_fillets():
    assert score_product_name("salmon fillets", "Wild Scottish Mackerel Fillets In Brine") == 0.0
    assert score_product_name("salmon fillets", "Bone In Salmon Fillets", "Aoraki") > 0


def test_tenderbasted_thigh_packs_allowed():
    assert score_product_name("chicken thighs", "Tender Basted Chicken Thighs", "Pams") > 0


def test_freshchoice_per_kg_courgette_not_charged_as_each():
    assert is_weight_priced(
        "UNITS",
        display="Approx. 6 units per kg",
        product_name="Courgettes (Approx. 6 units per kg)",
    )
    qty, unit, total = price_purchase(
        ingredient="zucchini",
        quantity=1,
        unit="each",
        unit_price=21.99,
        sale_type="UNITS",
        display="Approx. 6 units per kg",
        product_name="Courgettes (Approx. 6 units per kg)",
        household_size=2,
    )
    assert unit == "kg"
    assert total < 12  # was wrongly $21.99 as 1 each


def test_loose_chicken_breast_high_unit_price_treated_as_per_kg():
    qty, unit, total = price_purchase(
        ingredient="chicken breast",
        quantity=1,
        unit="each",
        unit_price=21.99,
        sale_type="UNITS",
        display="",
        product_name="Chicken Breast Fillets Skin Off",
        household_size=2,
    )
    assert unit == "kg"
    assert total < 12  # was wrongly $21.99 as 1 each
