"""Changing chef/prefs must not leave a stale meal plan for the next generate."""

from __future__ import annotations

import asyncio

from agent.orchestrator import MealAgentOrchestrator
from shared.models import (
    Ingredient,
    Meal,
    MealPlan,
    MealSlot,
    MealsRequested,
    UserProfile,
)


def _sample_plan(name: str = "Old Chef Dinner") -> MealPlan:
    return MealPlan(
        meals=[
            Meal(
                name=name,
                slot=MealSlot.DINNER,
                day_label="Monday",
                description="leftover from previous chef",
                ingredients=[Ingredient(name="chicken", quantity=500, unit="g")],
                steps=["Cook"],
            )
        ],
        shared_ingredients=[Ingredient(name="chicken", quantity=500, unit="g")],
        chef_notes="Notes from the previous chef",
    )


def test_run_discovery_clears_existing_meal_plan():
    orch = MealAgentOrchestrator()
    orch.state.meal_plan = _sample_plan()
    orch.state.plan_approved = True

    profile = asyncio.run(
        orch.run_discovery(
            {
                "household_size": 2,
                "days": 7,
                "dinner_count": 5,
                "lunch_count": 0,
                "snack_count": 0,
                "allergies": "",
                "mandatory_items": "",
                "pantry_items": "",
                "likes": "",
                "dislikes": "",
                "other_instructions": "",
                "budget_nzd": 150,
                "store_name": "",
                "simplicity": "simple",
                "brand_preference": "mixed",
                "chef_id": "premium_kenji",
                "lunch_mode": "original",
            }
        )
    )

    assert profile.chef_id == "premium_kenji"
    assert orch.state.meal_plan is None
    assert orch.state.plan_approved is False


def test_generate_plan_clears_before_llm(monkeypatch):
    orch = MealAgentOrchestrator()
    orch.state.meal_plan = _sample_plan()

    async def fake_generate(profile: UserProfile, *, fallback_on_error: bool = True) -> MealPlan:
        # Mid-generation the previous plan must already be gone (SSE recovery safety).
        assert orch.state.meal_plan is None
        return _sample_plan(name="New Chef Dinner")

    monkeypatch.setattr(orch.planner, "generate", fake_generate)

    profile = UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=5),
        chef_id="premium_elena",
        budget_nzd=150,
    )
    plan = asyncio.run(orch.generate_plan(profile))
    assert plan.meals[0].name == "New Chef Dinner"
    assert orch.state.meal_plan is not None
    assert orch.state.meal_plan.meals[0].name == "New Chef Dinner"
