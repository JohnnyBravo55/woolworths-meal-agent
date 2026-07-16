"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Cookie, Header, HTTPException

from meal_agent_api.auth import user_store
from meal_agent_api.session_store import AgentSession, store

SESSION_COOKIE = "meal_agent_session"
AUTH_COOKIE = "meal_agent_auth"


def get_session(
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> AgentSession:
    sid = session_id or x_session_id
    if not sid:
        raise HTTPException(status_code=401, detail="No session — call POST /api/session/start")
    try:
        return store.require(sid)
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="Session expired") from exc


def get_optional_user(
    auth_token: str | None = Cookie(default=None, alias=AUTH_COOKIE),
    x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
):
    token = auth_token or x_auth_token
    return user_store.get_by_token(token) if token else None
