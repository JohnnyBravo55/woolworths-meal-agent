"""Tests for search helpers."""

from shared.models import UserProfile, MealsRequested
from woolworths_adapter.search_helpers import is_plausible_match, search_queries_for


def _gf_profile() -> UserProfile:
    return UserProfile(
        household_size=2,
        allergies=["gluten"],
        budget_nzd=200,
        meals_requested=MealsRequested(dinner=5),
    )


def test_bell_pepper_rejects_black_pepper():
    assert is_plausible_match("bell pepper", "woolworths black pepper ground") is False
    assert is_plausible_match("bell pepper", "woolworths capsicum red") is True


def test_avocado_rejects_dressing():
    assert is_plausible_match("avocado", "eta avocado & garlic dressing") is False
    assert is_plausible_match("avocado", "avocado hass each") is True


def test_cocoa_rejects_laundry():
    assert is_plausible_match("cocoa powder", "fab laundry powder fresh blossoms") is False


def test_chicken_breast_rejects_roast_shredded():
    assert is_plausible_match("chicken breast", "woolworths shredded roast chicken") is False
    assert is_plausible_match("chicken breast", "woolworths chicken breast skin on bulk pack") is True


def test_zucchini_rejects_pickled():
    assert is_plausible_match("zucchini", "woolworths pickled zucchini slices") is False
    assert is_plausible_match("zucchini", "zucchini each") is True
    assert is_plausible_match("zucchini", "fresh vegetable courgette") is True
    assert is_plausible_match("zucchini", "woolworths fresh vegetable courgette") is True


def test_bok_choy_accepts_pak_choy():
    assert is_plausible_match("bok choy", "fresh vegetable baby pak choy bunch") is True
    assert is_plausible_match("bok choy", "shanghai pak choy prepacked") is True
    assert is_plausible_match("bok choy", "choy sum fresh vegetable") is False


def test_tinned_tomatoes_accept_diced():
    assert is_plausible_match("tinned tomatoes", "essentials diced tomatoes") is True
    assert is_plausible_match("diced tomatoes", "woolworths diced tomatoes italian") is True
    assert is_plausible_match("tinned tomatoes", "fresh tomatoes loose") is False


def test_wholemeal_wraps_match():
    assert is_plausible_match("whole wheat wraps", "farrah's wraps wholemeal") is True
    assert is_plausible_match("wholemeal wraps", "woolworths wraps wholemeal") is True
    assert is_plausible_match("whole wheat wraps", "farrah's wraps premium white") is False


def test_minced_beef_accepts_beef_mince():
    assert is_plausible_match("minced beef", "woolworths nz beef mince grass fed 18% fat") is True
    assert is_plausible_match("beef mince", "woolworths nz beef mince grass fed 5% fat") is True


def test_salmon_rejects_crumbed():
    assert is_plausible_match("salmon fillets", "sealord crumbed fish fillets") is False
    assert is_plausible_match("salmon fillets", "salmon fillet skin on") is True


def test_salmon_rejects_canned_brine():
    assert is_plausible_match("salmon fillets", "diplomats salmon fillets in brine") is False
    assert is_plausible_match("salmon fillets", "woolworths pink salmon canned") is False
    assert is_plausible_match("salmon fillets", "woolworths nz salmon fillets skin on") is True
    assert is_plausible_match("salmon fillets", "shore mariner salmon portions") is True
    assert is_plausible_match("chili flakes", "woolworths chilli flakes") is True
    assert is_plausible_match("chilli flakes", "woolworths chilli flakes") is True


def test_capsicum_rejects_bean_snack_mix():
    assert is_plausible_match(
        "capsicum",
        "edgell snacktime red kidney beans with corn, capsicum & lime",
    ) is False
    assert is_plausible_match("capsicum", "fresh vegetable capsicum green") is True


def test_miso_paste_rejects_instant_soup():
    assert is_plausible_match(
        "miso paste",
        "marukome instant soup miso paste wakame seaweed",
    ) is False
    assert is_plausible_match("miso paste", "hikari miso paste white") is True
    assert is_plausible_match("miso paste", "organic miso paste") is True


def test_apples_reject_puree():
    assert is_plausible_match("apples", "woolworths fruit puree apples") is False


def test_beef_strips_rejects_dog_treats():
    assert is_plausible_match("beef strips", "vitapet dog treats beef munchy strips") is False
    assert is_plausible_match("beef strips", "woolworths beef premium stir-fry") is True
    assert is_plausible_match("beef strips", "woolworths angus beef stir-fry") is True


def test_beef_strips_accepts_real_beef():
    assert is_plausible_match("beef strips", "woolworths beef stir fry strips") is True


def test_nori_rejects_rice_cakes():
    assert is_plausible_match("nori sheets", "sunrice thin rice cakes sour cream") is False


def test_beef_strips_rejects_chicken_strips():
    assert is_plausible_match("beef strips", "tegel chicken strips free range") is False


def test_beef_strips_rejects_corned_beef():
    assert is_plausible_match("beef strips", "woolworths beef corned silverside") is False
    queries = search_queries_for("broccoli")
    assert queries[0] == "broccoli head"


def test_garlic_aliases():
    queries = search_queries_for("garlic")
    assert "garlic bulb" in queries


def test_sesame_oil_rejects_canola():
    assert is_plausible_match("sesame oil", "woolworths canola oil") is False
    assert is_plausible_match("sesame oil", "woolworths sesame oil") is True


def test_face_mask_rejected_for_cucumber():
    assert is_plausible_match(
        "cucumber",
        "glow lab hydrating glow mask aloe vera & cucumber",
    ) is False
    assert is_plausible_match("cucumber", "cucumber each") is True


def test_capsicum_rejects_hummus_dip():
    assert is_plausible_match("capsicum", "lisas hummus chargrilled capsicum") is False
    assert is_plausible_match("capsicum", "fresh vegetable capsicum green") is True
    assert is_plausible_match("bell pepper", "prep set go frozen sliced capsicum") is True


def test_cucumber_rejects_drink_mixer():
    assert is_plausible_match(
        "cucumber",
        "barker's drink mixers lemon lime cucumber & mint",
    ) is False
    assert is_plausible_match("cucumber", "woolworths cucumbers baby") is True
    assert is_plausible_match("cucumber", "fresh vegetable cucumber") is True


def test_salmon_fillets_reject_steamed_pouch():
    assert is_plausible_match("salmon fillets", "ocean blue salmon steamed natural") is False
    assert is_plausible_match("salmon fillets", "woolworths nz salmon fillets skin on") is True


def test_gf_crackers_search_rice_first_for_kenji():
    queries = search_queries_for("crackers", _gf_profile(), "premium_kenji")
    assert queries[0] == "rice crackers"


def test_cheese_rejects_snack_sticks():
    assert is_plausible_match("cheese", "mainland cheese snack sticks 8 pack") is False
    assert is_plausible_match("cheese", "mainland tasty cheese block") is True


def test_taco_shells_match():
    assert is_plausible_match("taco shells", "old el paso taco shells hard") is True
    assert is_plausible_match("taco shells", "tomato pasta sauce") is False


def test_mixed_salad_leaves_queries():
    queries = search_queries_for("mixed salad leaves")
    assert "mixed salad" in queries
