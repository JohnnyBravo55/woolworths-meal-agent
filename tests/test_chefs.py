"""Tests for chef personas."""

from meal_planner.chefs import CHEFS, get_chef, is_premium_chef, list_chefs


def test_basic_chef_exists():
    chef = get_chef("basic_sam")
    assert chef.tier == "basic"
    assert not is_premium_chef(chef.id)


def test_premium_chefs_count():
    premium = [c for c in list_chefs() if c.tier == "premium"]
    assert len(premium) == 5
    ids = {c.id for c in premium}
    assert ids == {
        "premium_elena",
        "premium_kenji",
        "premium_moana",
        "premium_alex",
        "premium_amara",
    }


def test_chefs_have_portrait_images():
    for chef in list_chefs():
        assert chef.avatar_image.startswith("/chefs/")
        assert chef.avatar_image.endswith(".png")


def test_premium_chefs_have_regional_prompts():
    for chef_id in (
        "premium_elena",
        "premium_kenji",
        "premium_moana",
        "premium_alex",
        "premium_amara",
    ):
        chef = CHEFS[chef_id]
        assert len(chef.system_prompt) > 100
        assert "Woolworths NZ" in chef.system_prompt


def test_sam_prompt_is_quality_generalist():
    sam = get_chef("basic_sam")
    assert sam.tier == "basic"
    assert "generalist" in sam.system_prompt.lower() or "NOT tied to one cuisine" in sam.system_prompt
    assert len(sam.system_prompt) > 200


def test_unknown_chef_falls_back_to_basic():
    assert get_chef("unknown").id == "basic_sam"
