"""NDA acceptance endpoint + Google Sheets webhook."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_agent_api.main import app
from meal_agent_api.nda import NdaAcceptance, NdaStore, append_nda_to_sheet


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


def test_nda_accept_stores_and_sheets(nda_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    sent: list = []

    def fake_sheet(record) -> None:
        sent.append(record)

    monkeypatch.setattr("meal_agent_api.main.append_nda_to_sheet", fake_sheet)
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
    monkeypatch.setattr("meal_agent_api.main.append_nda_to_sheet", lambda _r: None)
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


def test_nda_accept_sheet_failure_returns_503(nda_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")

    def boom(_record) -> None:
        raise RuntimeError("Sheets down")

    monkeypatch.setattr("meal_agent_api.main.append_nda_to_sheet", boom)
    client = TestClient(app)
    res = client.post(
        "/api/nda/accept",
        json={"full_name": "Jane Tester", "agreed": True, "nda_version": "1"},
    )
    assert res.status_code == 503
    rows = json.loads(nda_file.read_text(encoding="utf-8"))
    assert len(rows) == 1


def test_append_nda_to_sheet_posts_webhook(monkeypatch: pytest.MonkeyPatch):
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

    monkeypatch.setattr("meal_agent_api.nda.httpx.post", fake_post)
    record = NdaAcceptance(
        id="abc",
        full_name="Jane Tester",
        nda_version="1",
        accepted_at="2026-07-20T00:00:00+00:00",
        user_agent="pytest",
        client_ip="1.2.3.4",
    )
    append_nda_to_sheet(record)
    assert calls[0]["url"] == "https://script.google.com/macros/s/fake/exec"
    assert calls[0]["json"]["secret"] == "test-secret"
    assert calls[0]["json"]["full_name"] == "Jane Tester"
    assert calls[0]["json"]["client_ip"] == "1.2.3.4"


def test_append_nda_to_sheet_rejects_ok_false(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NDA_SHEETS_WEBHOOK_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("NDA_SHEETS_SECRET", "test-secret")

    class FakeResponse:
        status_code = 200
        text = '{"ok":false,"error":"bad secret"}'

        def json(self):
            return {"ok": False, "error": "bad secret"}

    monkeypatch.setattr("meal_agent_api.nda.httpx.post", lambda *a, **k: FakeResponse())
    record = NdaAcceptance(
        id="abc",
        full_name="Jane Tester",
        nda_version="1",
        accepted_at="2026-07-20T00:00:00+00:00",
    )
    with pytest.raises(RuntimeError, match="rejected"):
        append_nda_to_sheet(record)
