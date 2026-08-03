"""Phased conversation flow for user intake."""

from __future__ import annotations

import json
from pathlib import Path

from shared.allergy import normalize_mandatory_for_allergies
from shared.models import (
    AgentPhase,
    BrandPreference,
    BudgetMode,
    ConversationState,
    LunchMode,
    MealsRequested,
    SimplicityLevel,
    UserProfile,
)
from shared.portions import age_bands_match_children, age_bands_sum

# Used when the user leaves weekly budget blank (optional preference).
_DEFAULT_SOFT_BUDGET_NZD = 200.0


def _budget_nzd_from_answers(answers: dict) -> float:
    raw = answers.get("budget_nzd", None)
    if raw is None or raw == "":
        return _DEFAULT_SOFT_BUDGET_NZD
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_SOFT_BUDGET_NZD
    if value <= 0:
        return _DEFAULT_SOFT_BUDGET_NZD
    return value


def _budget_mode_from_answers(answers: dict) -> BudgetMode:
    raw = answers.get("budget_nzd", None)
    if raw is None or raw == "":
        return BudgetMode.SOFT
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return BudgetMode.SOFT
    return BudgetMode.HARD if value > 0 else BudgetMode.SOFT


class ConversationManager:
    """Manages discovery intake and phase transitions."""

    QUESTIONS = [
        ("adults", "How many adult portions (people 13+)?", int, {"default": 2}),
        ("children_under_13", "How many child portions (12 and under)?", int, {"default": 0}),
        ("days", "How many days should this shop cover?", int, {"default": 7}),
        (
            "dinner_count",
            "How many dinners do you need?",
            int,
            {"default": 5},
        ),
        (
            "lunch_count",
            "How many lunches?",
            int,
            {"default": 0},
        ),
        (
            "snack_count",
            "How many snack portions?",
            int,
            {"default": 0},
        ),
        (
            "allergies",
            "Any allergies? (comma-separated, or leave blank)",
            str,
            {"default": ""},
        ),
        (
            "mandatory_items",
            "Mandatory items each shop? (comma-separated, e.g. milk, bread)",
            str,
            {"default": ""},
        ),
        (
            "pantry_items",
            "Items you already have at home? (comma-separated — chef uses them, won't shop)",
            str,
            {"default": ""},
        ),
        (
            "likes",
            "Foods you enjoy? (comma-separated)",
            str,
            {"default": ""},
        ),
        (
            "dislikes",
            "Foods to avoid? (comma-separated)",
            str,
            {"default": ""},
        ),
        (
            "other_instructions",
            "Other instructions for the chef? (free text, optional)",
            str,
            {"default": ""},
        ),
        (
            "budget_nzd",
            "Weekly grocery budget in NZD?",
            float,
            {"default": 150.0},
        ),
        (
            "store_name",
            "Which Woolworths store? (name or suburb)",
            str,
            {"default": ""},
        ),
        (
            "simplicity",
            "Meal complexity? (simple/moderate/ambitious)",
            str,
            {"default": "simple"},
        ),
        (
            "brand_preference",
            "Brand preference? (budget/mixed/premium)",
            str,
            {"default": "mixed"},
        ),
    ]

    def __init__(self):
        self.state = ConversationState()

    def create_profile_from_answers(self, answers: dict) -> UserProfile:
        def split_list(value: str) -> list[str]:
            if not value or not value.strip():
                return []
            return [v.strip() for v in value.split(",") if v.strip()]

        simplicity_raw = answers.get("simplicity", "simple").lower()
        try:
            simplicity = SimplicityLevel(simplicity_raw)
        except ValueError:
            simplicity = SimplicityLevel.SIMPLE

        brand_raw = answers.get("brand_preference", "mixed").lower()
        try:
            brand_preference = BrandPreference(brand_raw)
        except ValueError:
            brand_preference = BrandPreference.MIXED

        lunch_raw = str(answers.get("lunch_mode", "original")).lower()
        try:
            lunch_mode = LunchMode(lunch_raw)
        except ValueError:
            lunch_mode = LunchMode.ORIGINAL

        allergies = split_list(str(answers.get("allergies", "")))

        adults_raw = answers.get("adults", None)
        children_raw = answers.get("children_under_13", None)
        if adults_raw is None and children_raw is None:
            adults = int(answers.get("household_size", 2))
            children_under_13 = 0
        else:
            adults = int(adults_raw if adults_raw is not None else 2)
            children_under_13 = int(children_raw if children_raw is not None else 0)
        bands_raw = answers.get("children_age_bands") or {}
        if not isinstance(bands_raw, dict):
            bands_raw = {}
        children_age_bands = {
            "1-3": int(bands_raw.get("1-3", 0) or 0),
            "4-6": int(bands_raw.get("4-6", 0) or 0),
            "7-9": int(bands_raw.get("7-9", 0) or 0),
            "10-12": int(bands_raw.get("10-12", 0) or 0),
        }
        if children_under_13 > 0 and age_bands_sum(children_age_bands) == 0:
            # CLI / sparse answers: default unassigned kids to the mid band.
            children_age_bands = {
                "1-3": 0,
                "4-6": 0,
                "7-9": children_under_13,
                "10-12": 0,
            }
        elif children_under_13 > 0 and not age_bands_match_children(
            children_age_bands, children_under_13
        ):
            raise ValueError("Assign an age for each child")

        profile = UserProfile(
            adults=adults,
            children_under_13=children_under_13,
            children_age_bands=children_age_bands,
            days=int(answers.get("days", 7)),
            meals_requested=MealsRequested(
                dinner=int(answers.get("dinner_count", 5)),
                lunch=int(answers.get("lunch_count", 0)),
                snacks=int(answers.get("snack_count", 0)),
            ),
            allergies=allergies,
            mandatory_items=normalize_mandatory_for_allergies(
                split_list(str(answers.get("mandatory_items", ""))),
                allergies=allergies,
            ),
            pantry_items=split_list(str(answers.get("pantry_items", ""))),
            likes=split_list(str(answers.get("likes", ""))),
            dislikes=split_list(str(answers.get("dislikes", ""))),
            other_instructions=str(answers.get("other_instructions", "") or "").strip(),
            budget_nzd=_budget_nzd_from_answers(answers),
            budget_mode=_budget_mode_from_answers(answers),
            store_name=str(answers.get("store_name", "")),
            store_id=str(answers.get("store_id", "")),
            simplicity=simplicity,
            brand_preference=brand_preference,
            lunch_mode=lunch_mode,
            chef_id=str(answers.get("chef_id") or "basic_sam"),
        )

        if "gluten" in profile.allergies and "gluten-free" not in profile.dietary_preferences:
            profile.dietary_preferences.append("gluten-free")

        self.state.profile = profile
        self.state.advance_to(AgentPhase.PLAN_DRAFT)
        return profile

    @staticmethod
    def load_answers(path: Path | str) -> dict:
        """Load saved intake answers from a JSON profile file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        # Strip metadata keys
        return {k: v for k, v in data.items() if not k.startswith("_") and k != "name"}

    @staticmethod
    def save_answers(path: Path | str, answers: dict, *, name: str = "") -> Path:
        """Save intake answers for reuse in test runs."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"name": name, **answers}
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out

    def profile_from_file(self, path: Path | str) -> UserProfile:
        return self.create_profile_from_answers(self.load_answers(path))

    @staticmethod
    def sample_profile() -> UserProfile:
        """Demo profile for non-interactive runs."""
        return UserProfile(
            household_size=2,
            days=7,
            meals_requested=MealsRequested(dinner=3, lunch=2, snacks=1),
            dietary_preferences=["balanced"],
            allergies=[],
            mandatory_items=["milk", "bread"],
            likes=["chicken", "pasta"],
            dislikes=["coriander"],
            budget_nzd=120.0,
            budget_mode=BudgetMode.HARD,
            store_name="Auckland Central",
            simplicity=SimplicityLevel.SIMPLE,
            brand_preference=BrandPreference.MIXED,
        )

    def confirm_allergies(self, profile: UserProfile) -> str:
        if not profile.allergies:
            return "No allergies recorded."
        return (
            f"ALLERGY CHECK: You listed {', '.join(profile.allergies)}. "
            "These will be hard-blocked from all meals and products."
        )
