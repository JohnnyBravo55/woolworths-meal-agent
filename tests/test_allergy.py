"""Tests for allergy safety."""

from shared.allergy import (
    ingredient_conflicts_allergies,
    is_product_safe_for_profile,
    normalize_mandatory_for_allergies,
    product_contains_gluten,
)
from shared.models import MealsRequested, UserProfile


def _gf_profile() -> UserProfile:
    return UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=5),
        budget_nzd=200,
        allergies=["gluten"],
    )


def test_banana_bread_blocked_for_gluten_allergy():
    assert product_contains_gluten("woolworths banana bread sliced") is True
    assert is_product_safe_for_profile(
        "woolworths banana bread sliced", "woolworths", _gf_profile()
    ) is False


def test_gluten_free_bread_allowed():
    assert is_product_safe_for_profile(
        "vogels gluten free bread", "vogels", _gf_profile(), ingredient_name="gluten free bread"
    ) is True


def test_ingredient_bread_blocked_without_gf_label():
    assert ingredient_conflicts_allergies("banana bread", _gf_profile()) is True
    assert ingredient_conflicts_allergies("gluten free bread", _gf_profile()) is False


def test_mandatory_bread_becomes_gluten_free():
    items = normalize_mandatory_for_allergies(["milk", "bread"], allergies=["gluten"])
    assert items == ["milk", "gluten free bread"]


def test_crumbed_fish_blocked_for_gluten_allergy():
    from shared.gluten_label import GlutenLabelAssessment, GlutenLabelStatus

    assessment = GlutenLabelAssessment(
        GlutenLabelStatus.CONTAINS, ["Allergen statement: Gluten, Wheat"]
    )
    assert is_product_safe_for_profile(
        "sealord crumbed fish fillets",
        "sealord",
        _gf_profile(),
        ingredient_name="salmon fillets",
        label_assessment=assessment,
    ) is False
    assert is_product_safe_for_profile(
        "salmon fillet skin on",
        "woolworths",
        _gf_profile(),
        ingredient_name="salmon fillets",
    ) is True


def test_rice_crackers_not_gluten():
    assert product_contains_gluten("sakata rice crackers original") is False
    assert is_product_safe_for_profile(
        "sakata rice crackers original",
        "sakata",
        _gf_profile(),
        ingredient_name="crackers",
    ) is True
