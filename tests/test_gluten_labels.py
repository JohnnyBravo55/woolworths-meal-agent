"""Tests for Woolworths label gluten assessment."""

from shared.gluten_label import GlutenLabelStatus, ProductLabelInfo, assess_gluten_label


def test_sealord_crumbed_fish_contains_gluten():
    label = ProductLabelInfo(
        allergens=["Fish, Milk, Gluten, Soy, Wheat"],
        ingredients=[
            "Hoki (Fish) (50%), Classic Crumb (50%) (Wheat Flour, Vegetable Oils, Water, Salt)."
        ],
    )
    result = assess_gluten_label(label)
    assert result.status == GlutenLabelStatus.CONTAINS
    assert any("Wheat" in r or "Allergen" in r for r in result.reasons)


def test_may_contain_gluten_is_traces_not_blocked():
    label = ProductLabelInfo(
        allergens=["May be present: Peanuts, Tree Nuts, Gluten"],
        ingredients=["Milk Chocolate (Sugar, Cocoa Mass, Milk Powder)."],
    )
    result = assess_gluten_label(label)
    assert result.status == GlutenLabelStatus.TRACES
    assert result.user_warning is not None


def test_contains_and_may_contain_parsed():
    label = ProductLabelInfo(
        allergens=["Contains: Milk, Soy, May contain: Peanut, Tree Nuts, Gluten"],
        ingredients=["Milk Chocolate (Sugar, Cocoa Mass)."],
    )
    result = assess_gluten_label(label)
    assert result.status == GlutenLabelStatus.TRACES


def test_gluten_free_bread_safe():
    label = ProductLabelInfo(
        claims=["Gluten Free"],
        allergens=["Egg"],
        ingredients=["Water, Tapioca Starch, Rice Flour, Egg White, Canola Oil."],
    )
    result = assess_gluten_label(label)
    assert result.status == GlutenLabelStatus.SAFE


def test_wheat_flour_in_ingredients_contains():
    label = ProductLabelInfo(
        ingredients=["Sugar, Wheat Flour, Cocoa Powder."],
        allergens=[],
    )
    result = assess_gluten_label(label)
    assert result.status == GlutenLabelStatus.CONTAINS


def test_allergen_maybe_present_traces():
    label = ProductLabelInfo(
        allergens=["Peanuts"],
        allergen_maybe_present="Tree Nuts, Sesame, Gluten",
        ingredients=["Hi-Oleic Peanuts"],
    )
    result = assess_gluten_label(label)
    assert result.status == GlutenLabelStatus.TRACES


def test_empty_label_unknown():
    result = assess_gluten_label(ProductLabelInfo())
    assert result.status == GlutenLabelStatus.UNKNOWN
