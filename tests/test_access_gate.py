"""Shared access-code gate for hosted tester deploys."""

from fastapi.testclient import TestClient

from meal_agent_api.access_gate import access_code_ok
from meal_agent_api.main import app


def test_access_code_ok_compare():
    assert access_code_ok("usertest1", "usertest1")
    assert not access_code_ok("wrong", "usertest1")
    assert not access_code_ok(None, "usertest1")
    assert not access_code_ok("", "usertest1")


def test_health_open_when_gate_enabled(monkeypatch):
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "usertest1")
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200


def test_api_requires_access_code(monkeypatch):
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "usertest1")
    client = TestClient(app)
    denied = client.post("/api/session/start")
    assert denied.status_code == 401

    ok = client.post("/api/session/start", headers={"X-Access-Code": "usertest1"})
    assert ok.status_code == 200
    assert "session_id" in ok.json()


def test_api_open_when_gate_disabled(monkeypatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    client = TestClient(app)
    res = client.post("/api/session/start")
    assert res.status_code == 200
