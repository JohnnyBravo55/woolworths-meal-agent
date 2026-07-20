"""Feedback submit endpoint + Google Sheets webhook."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_agent_api.feedback import FeedbackSubmission, append_feedback_to_sheet
from meal_agent_api.main import app


VALID_BODY = {
    "meal_plan_useful": "Useful",
    "most_valuable": "Shopping list",
    "use_again": "Likely",
    "if_never_public": "Disappointed",
    "premium_subscribe": "Very likely",
    "improve": "Faster plan generation",
    "session_id": "sess-1",
}


@pytest.fixture()
def feedback_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from meal_agent_api.feedback import FeedbackStore

    path = tmp_path / "feedback_submissions.json"
    store = FeedbackStore(path)
    monkeypatch.setattr("meal_agent_api.main.feedback_store", store)
    monkeypatch.setattr("meal_agent_api.feedback.feedback_store", store)
    return path


def test_append_feedback_to_sheet_noop_without_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NDA_SHEETS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NDA_SHEETS_SECRET", raising=False)
    calls: list = []
    monkeypatch.setattr("meal_agent_api.feedback.httpx.post", lambda *a, **k: calls.append(1))
    append_feedback_to_sheet(
        FeedbackSubmission(
            id="abc",
            submitted_at="2026-07-20T00:00:00+00:00",
            session_id="s1",
            meal_plan_useful="Useful",
            most_valuable="Shopping list",
            use_again="Likely",
            if_never_public="Disappointed",
            premium_subscribe="Very likely",
            improve="",
            user_agent="pytest",
        )
    )
    assert calls == []


def test_append_feedback_to_sheet_posts_webhook(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NDA_SHEETS_WEBHOOK_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("NDA_SHEETS_SECRET", "test-secret")
    calls: list[dict] = []

    class FakeResponse:
        status_code = 200
        text = '{"ok":true}'

        def json(self):
            return {"ok": True}

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("meal_agent_api.feedback.httpx.post", fake_post)
    append_feedback_to_sheet(
        FeedbackSubmission(
            id="abc",
            submitted_at="2026-07-20T00:00:00+00:00",
            session_id="s1",
            meal_plan_useful="Useful",
            most_valuable="Shopping list",
            use_again="Likely",
            if_never_public="Disappointed",
            premium_subscribe="Very likely",
            improve="note",
            user_agent="pytest",
        )
    )
    assert calls[0]["json"]["type"] == "feedback"
    assert calls[0]["json"]["secret"] == "test-secret"
    assert calls[0]["json"]["meal_plan_useful"] == "Useful"
    assert calls[0]["json"]["premium_subscribe"] == "Very likely"
