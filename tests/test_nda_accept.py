"""NDA acceptance endpoint + store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_agent_api.main import app
from meal_agent_api.nda import NdaStore, send_nda_notification


@pytest.fixture()
def nda_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "nda_acceptances.json"
    store = NdaStore(path)
    monkeypatch.setattr("meal_agent_api.main.nda_store", store)
    monkeypatch.setattr("meal_agent_api.nda.nda_store", store)
    return path


def test_nda_accept_requires_name_and_agree(nda_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    client = TestClient(app)

    missing_name = client.post(
        "/api/nda/accept",
        json={"full_name": "  ", "agreed": True, "nda_version": "1"},
    )
    assert missing_name.status_code == 400

    not_agreed = client.post(
        "/api/nda/accept",
        json={"full_name": "Jane Tester", "agreed": False, "nda_version": "1"},
    )
    assert not_agreed.status_code == 400


def test_nda_accept_stores_and_emails(nda_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    sent: list = []

    def fake_send(record) -> None:
        sent.append(record)

    monkeypatch.setattr("meal_agent_api.main.send_nda_notification", fake_send)
    client = TestClient(app)
    res = client.post(
        "/api/nda/accept",
        json={"full_name": "Jane Tester", "agreed": True, "nda_version": "1"},
        headers={"User-Agent": "pytest-agent"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["full_name"] == "Jane Tester"
    assert body["nda_version"] == "1"
    assert body["id"]
    assert body["accepted_at"]

    rows = json.loads(nda_file.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Jane Tester"
    assert rows[0]["user_agent"] == "pytest-agent"
    assert len(sent) == 1
    assert sent[0].full_name == "Jane Tester"


def test_nda_accept_gated_by_access_code(nda_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "usertest1")
    monkeypatch.setattr("meal_agent_api.main.send_nda_notification", lambda _r: None)
    client = TestClient(app)

    denied = client.post(
        "/api/nda/accept",
        json={"full_name": "Jane Tester", "agreed": True, "nda_version": "1"},
    )
    assert denied.status_code == 401

    ok = client.post(
        "/api/nda/accept",
        headers={"X-Access-Code": "usertest1"},
        json={"full_name": "Jane Tester", "agreed": True, "nda_version": "1"},
    )
    assert ok.status_code == 200


def test_nda_accept_email_failure_returns_503(nda_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")

    def boom(_record) -> None:
        raise RuntimeError("Resend down")

    monkeypatch.setattr("meal_agent_api.main.send_nda_notification", boom)
    client = TestClient(app)
    res = client.post(
        "/api/nda/accept",
        json={"full_name": "Jane Tester", "agreed": True, "nda_version": "1"},
    )
    assert res.status_code == 503
    rows = json.loads(nda_file.read_text(encoding="utf-8"))
    assert len(rows) == 1


def test_send_nda_notification_calls_resend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("NDA_FROM_EMAIL", "Beta <onboarding@resend.dev>")
    monkeypatch.setenv("NDA_NOTIFY_EMAIL", "marcus@pyxstudio.nz")

    calls: list[dict] = []

    class FakeResponse:
        status_code = 200
        text = "ok"

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("meal_agent_api.nda.httpx.post", fake_post)
    from meal_agent_api.nda import NdaAcceptance

    record = NdaAcceptance(
        id="abc",
        full_name="Jane Tester",
        nda_version="1",
        accepted_at="2026-07-20T00:00:00+00:00",
    )
    send_nda_notification(record)
    assert calls[0]["url"] == "https://api.resend.com/emails"
    assert calls[0]["json"]["to"] == ["marcus@pyxstudio.nz"]
    assert "Jane Tester" in calls[0]["json"]["text"]
