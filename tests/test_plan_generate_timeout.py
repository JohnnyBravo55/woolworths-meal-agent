"""Plan generate must not hang forever when OpenAI stalls."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from meal_planner.planner import MealPlanner, MealPlanLLMError
from shared.models import MealsRequested, UserProfile


def _profile(**kwargs) -> UserProfile:
    defaults = dict(
        household_size=2,
        meals_requested=MealsRequested(dinner=2, lunch=1),
        budget_nzd=100,
        chef_id="basic_sam",
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


@pytest.mark.asyncio
async def test_llm_generate_times_out_and_falls_back_for_basic_chef():
    """Stalled OpenAI calls must fail fast so Cloudflare/Render do not drop the stream."""
    planner = MealPlanner(api_key="sk-test")
    planner.LLM_TIMEOUT_SECONDS = 0.05

    async def hang(*_a, **_k):
        await asyncio.sleep(3600)

    fake_client = MagicMock()
    fake_client.chat.completions.create = hang

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        plan = await planner.generate(_profile(), fallback_on_error=True)

    assert plan is not None
    assert len(plan.meals) >= 1
    assert planner._last_llm_error
    assert "timed out" in planner._last_llm_error.lower() or "timeout" in planner._last_llm_error.lower()


@pytest.mark.asyncio
async def test_llm_generate_timeout_raises_for_premium_without_fallback():
    planner = MealPlanner(api_key="sk-test")
    planner.LLM_TIMEOUT_SECONDS = 0.05

    async def hang(*_a, **_k):
        await asyncio.sleep(3600)

    fake_client = MagicMock()
    fake_client.chat.completions.create = hang

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        with pytest.raises(MealPlanLLMError):
            await planner.generate(
                _profile(chef_id="premium_elena"),
                fallback_on_error=False,
            )
