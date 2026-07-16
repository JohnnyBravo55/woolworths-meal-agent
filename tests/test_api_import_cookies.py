"""API endpoint for mobile Woolworths cookie import."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from meal_agent_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_import_cookies_requires_session(client):
    res = client.post(
        "/api/session/woolworths/import-cookies",
        json={"cookies": [{"name": "a", "value": "b", "domain": ".woolworths.co.nz"}]},
    )
    assert res.status_code == 401


def test_import_cookies_rejects_empty(client):
    start = client.post("/api/session/start")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    res = client.post(
        "/api/session/woolworths/import-cookies",
        headers={"X-Session-Id": session_id},
        json={"cookies": []},
    )
    assert res.status_code == 400
    assert "No cookies" in res.json()["detail"]


def test_import_cookies_success(client, tmp_path, monkeypatch):
    start = client.post("/api/session/start")
    session_id = start.json()["session_id"]

    monkeypatch.setenv("WOOLIES_STATE_DIR", str(tmp_path))

    cookies = [
        {
            "name": "session",
            "value": "abc123",
            "domain": ".woolworths.co.nz",
            "path": "/",
            "expires": -1,
            "httpOnly": False,
            "secure": True,
            "sameSite": "Lax",
        },
        {
            "name": "auth",
            "value": "token",
            "domain": ".woolworths.co.nz",
            "path": "/",
        },
    ]

    with patch(
        "woolworths_adapter.client.WoolworthsAdapter.is_live",
        new_callable=AsyncMock,
        return_value=True,
    ):
        res = client.post(
            "/api/session/woolworths/import-cookies",
            headers={"X-Session-Id": session_id},
            json={"cookies": cookies},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["connected"] is True
    assert "Connected" in body["message"]


def test_import_cookies_fails_live_check(client, tmp_path, monkeypatch):
    start = client.post("/api/session/start")
    session_id = start.json()["session_id"]
    monkeypatch.setenv("WOOLIES_STATE_DIR", str(tmp_path))

    cookies = [
        {"name": "session", "value": "bad", "domain": ".woolworths.co.nz", "path": "/"},
    ]

    with patch(
        "woolworths_adapter.client.WoolworthsAdapter.is_live",
        new_callable=AsyncMock,
        return_value=False,
    ):
        res = client.post(
            "/api/session/woolworths/import-cookies",
            headers={"X-Session-Id": session_id},
            json={"cookies": cookies},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["connected"] is False
    assert "not verified" in body["message"].lower()
