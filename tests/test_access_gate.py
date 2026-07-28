"""Shared access-code gate for hosted tester deploys."""

from fastapi.testclient import TestClient

from meal_agent_api.access_gate import access_code_ok, required_access_codes
from meal_agent_api.main import app


def test_access_code_ok_compare():
    assert access_code_ok("usertest1", "usertest1")
    assert not access_code_ok("wrong", "usertest1")
    assert not access_code_ok(None, "usertest1")
    assert not access_code_ok("", "usertest1")


def test_access_code_ok_accepts_any_in_list():
    codes = [f"usertest{i}" for i in range(1, 51)]
    assert access_code_ok("usertest1", codes)
    assert access_code_ok("usertest25", codes)
    assert access_code_ok("usertest50", codes)
    assert not access_code_ok("usertest51", codes)
    assert not access_code_ok("usertest0", codes)


def test_required_access_codes_parses_csv(monkeypatch):
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "usertest1, usertest2, usertest50")
    assert required_access_codes() == ["usertest1", "usertest2", "usertest50"]


def test_health_open_when_gate_enabled(monkeypatch):
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "usertest1")
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    openai_probe = client.get("/api/health/openai")
    assert openai_probe.status_code == 200


def test_api_requires_access_code(monkeypatch):
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "usertest1")
    client = TestClient(app)
    denied = client.post("/api/session/start")
    assert denied.status_code == 401

    ok = client.post("/api/session/start", headers={"X-Access-Code": "usertest1"})
    assert ok.status_code == 200
    assert "session_id" in ok.json()


def test_api_accepts_any_csv_access_code(monkeypatch):
    codes = ",".join(f"usertest{i}" for i in range(1, 51))
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", codes)
    client = TestClient(app)

    denied = client.post("/api/session/start", headers={"X-Access-Code": "usertest51"})
    assert denied.status_code == 401

    for code in ("usertest1", "usertest25", "usertest50"):
        ok = client.post("/api/session/start", headers={"X-Access-Code": code})
        assert ok.status_code == 200, code
        assert "session_id" in ok.json()


def test_api_open_when_gate_disabled(monkeypatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    client = TestClient(app)
    res = client.post("/api/session/start")
    assert res.status_code == 200
