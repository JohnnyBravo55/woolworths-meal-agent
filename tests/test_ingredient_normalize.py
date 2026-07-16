"""Tests for ingredient name normalization."""

from meal_planner.ingredient_normalize import (
    normalize_ingredient_name,
    split_compound_ingredients,
)
from shared.models import Ingredient, Meal, MealSlot


def test_seasonal_fruits_becomes_apples():
    assert normalize_ingredient_name("mixed seasonal fruits") == "apples"
    assert normalize_ingredient_name("seasonal vegetables") == "stir fry vegetables"
    assert normalize_ingredient_name("mixed vegetables (carrots, broccoli)") == "stir fry vegetables"
    assert normalize_ingredient_name("vegetable stir-fry") == "stir fry vegetables"
    assert normalize_ingredient_name("vegetable stir fry mix") == "stir fry vegetables"
    assert normalize_ingredient_name("stir-fried vegetables") == "stir fry vegetables"
    assert normalize_ingredient_name("stir fried vegetables") == "stir fry vegetables"
    assert normalize_ingredient_name("tinned tomatoes") == "diced tomatoes"
    assert normalize_ingredient_name("whole wheat wraps") == "wholemeal wraps"
    assert normalize_ingredient_name("minced beef") == "beef mince"
    assert normalize_ingredient_name("ground beef") == "beef mince"
    assert normalize_ingredient_name("long-grain rice") == "long grain rice"
    assert normalize_ingredient_name("suya spice mix") == "cajun seasoning"


def test_butter_lettuce_splits():
    meal = Meal(
        name="Salad",
        slot=MealSlot.LUNCH,
        day_label="Monday",
        description="",
        ingredients=[Ingredient(name="butter lettuce", quantity=1, unit="head")],
        steps=[],
    )
    out = split_compound_ingredients([meal])
    names = {i.name for i in out[0].ingredients}
    assert "butter" in names
    assert "lettuce" in names


def test_mixed_salad_leaves_normalized():
    assert normalize_ingredient_name("mixed salad leaves") == "mixed salad greens"


def test_cooked_chicken_normalizes_to_chicken_breast():
    assert normalize_ingredient_name("cooked chicken") == "chicken breast"
    assert normalize_ingredient_name("chicken thigh fillets") == "chicken thighs"
    assert normalize_ingredient_name("chicken thigh fillet") == "chicken thighs"
    assert normalize_ingredient_name("grated cheese") == "cheese"
    assert normalize_ingredient_name("shredded cheese") == "cheese"
    assert normalize_ingredient_name("cooked rice") == "rice"
    assert normalize_ingredient_name("leftover cooked rice") == "leftover cooked rice"


def test_cooked_salmon_normalizes_to_salmon_fillets():
    assert normalize_ingredient_name("cooked salmon fillet") == "salmon fillets"
    assert normalize_ingredient_name("cooked salmon") == "salmon fillets"
    assert normalize_ingredient_name("leftover miso-glazed salmon") == "leftover miso-glazed salmon"


def test_sustainable_white_fish_normalizes():
    assert normalize_ingredient_name("sustainable white fish fillets") == "fish fillets"
    assert normalize_ingredient_name("white fish fillets") == "fish fillets"


def test_chili_spelling_normalizes_to_chilli():
    assert normalize_ingredient_name("chili flakes") == "chilli flakes"
    assert normalize_ingredient_name("chili powder") == "chilli powder"


def test_african_spice_mixes_normalize():
    assert normalize_ingredient_name("jollof spice mix") == "cajun seasoning"
    assert normalize_ingredient_name("okra spice mix") == "cajun seasoning"
    assert normalize_ingredient_name("peanut spice mix") == "peanut butter"


def test_lemon_wedges_normalize():
    assert normalize_ingredient_name("lemon wedges") == "lemons"
    assert normalize_ingredient_name("lime wedges") == "limes"


def test_watercress_normalizes_to_rocket():
    assert normalize_ingredient_name("watercress") == "rocket"


def test_plantain_normalizes_to_kumara():
    assert normalize_ingredient_name("plantain") == "kumara"
    assert normalize_ingredient_name("ripe plantain") == "kumara"


def test_carrot_and_mash_normalize():
    assert normalize_ingredient_name("carrot") == "carrots"
    assert normalize_ingredient_name("carrot / carrots") == "carrots"
    assert normalize_ingredient_name("kumara mash") == "kumara"
    assert normalize_ingredient_name("potato mash") == "potatoes"
    assert normalize_ingredient_name("lettuce leaves") == "lettuce"
