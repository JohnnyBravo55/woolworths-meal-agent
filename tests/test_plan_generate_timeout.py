"""Plan generate must not hang forever when OpenAI stalls — all chefs."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from meal_planner.openai_client import reset_openai_client_for_tests, stream_chat_json
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


@pytest.fixture(autouse=True)
def _reset_client():
    reset_openai_client_for_tests()
    yield
    reset_openai_client_for_tests()


@pytest.mark.asyncio
async def test_llm_timeout_falls_back_for_basic_chef_after_retry():
    planner = MealPlanner(api_key="sk-test")
    calls = {"n": 0}

    async def boom(**_kwargs):
        calls["n"] += 1
        raise TimeoutError("OpenAI meal planning timed out after 60s")

    with patch("meal_planner.openai_client.stream_chat_json", new=boom):
        plan = await planner.generate(_profile(), fallback_on_error=True)

    assert calls["n"] == 2
    assert plan is not None
    assert len(plan.meals) >= 1
    assert planner._last_llm_error
    assert "timed out" in planner._last_llm_error.lower()


@pytest.mark.asyncio
async def test_llm_timeout_retries_then_raises_for_premium():
    planner = MealPlanner(api_key="sk-test")
    calls = {"n": 0}

    async def boom(**_kwargs):
        calls["n"] += 1
        raise TimeoutError("OpenAI meal planning timed out after 60s")

    with patch("meal_planner.openai_client.stream_chat_json", new=boom):
        with pytest.raises(MealPlanLLMError):
            await planner.generate(
                _profile(chef_id="premium_elena"),
                fallback_on_error=False,
            )
    assert calls["n"] == 2, "all chefs get one retry on timeout"


@pytest.mark.asyncio
async def test_stream_chat_json_reports_progress():
    class Delta:
        def __init__(self, content):
            self.content = content

    class Choice:
        def __init__(self, content):
            self.delta = Delta(content)

    class Event:
        def __init__(self, content):
            self.choices = [Choice(content)]

    class FakeStream:
        def __init__(self, pieces):
            self._pieces = pieces

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._pieces):
                raise StopAsyncIteration
            piece = self._pieces[self._i]
            self._i += 1
            return Event(piece)

    class FakeCompletions:
        async def create(self, **_kwargs):
            return FakeStream(['{"ok":', " true}"])

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    seen: list[int] = []

    async def on_progress(n: int):
        seen.append(n)

    with patch("meal_planner.openai_client.get_async_openai", return_value=FakeClient()):
        content = await stream_chat_json(
            model="gpt-4o-mini",
            system="sys",
            user="user",
            api_key="sk-test",
            on_progress=on_progress,
        )
    assert content == '{"ok": true}'
    assert seen == [6, 12]


@pytest.mark.asyncio
async def test_stream_chat_json_times_out_slow_stream():
    class FakeStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(3600)
            raise StopAsyncIteration

    class FakeCompletions:
        async def create(self, **_kwargs):
            return FakeStream()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    with patch("meal_planner.openai_client.get_async_openai", return_value=FakeClient()):
        with pytest.raises(TimeoutError, match="timed out"):
            await stream_chat_json(
                model="gpt-4o-mini",
                system="sys",
                user="user",
                api_key="sk-test",
                timeout=0.05,
            )
