"""API health / OpenAI configuration status."""

from fastapi.testclient import TestClient

from meal_agent_api.main import app


def test_health_reports_openai_status(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["openai_configured"] is True
    assert body["openai_model"] == "gpt-4o-mini"


def test_health_openai_not_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("meal_agent_api.main.load_dotenv", lambda *a, **k: None)
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["openai_configured"] is False
