"""Optional shared access-code gate for hosted tester deployments."""

from __future__ import annotations

import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


ACCESS_CODE_HEADER = "X-Access-Code"

# Probes and public docs stay open when the gate is enabled.
_OPEN_PATHS = frozenset(
    {
        "/api/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


def required_access_code() -> str | None:
    code = os.environ.get("MEAL_AGENT_ACCESS_CODE", "").strip()
    return code or None


def access_code_ok(provided: str | None, expected: str) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(provided.strip(), expected)


class AccessCodeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        expected = required_access_code()
        if expected is None:
            return await call_next(request)

        # Let CORS preflight through; browser won't send X-Access-Code on OPTIONS.
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in _OPEN_PATHS or path.startswith("/chefs"):
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        provided = request.headers.get(ACCESS_CODE_HEADER)
        if access_code_ok(provided, expected):
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Access code required. Enter the tester code to continue."},
        )
