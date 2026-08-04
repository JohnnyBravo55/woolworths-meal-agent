"""Optional shared access-code gate for hosted tester deployments."""

from __future__ import annotations

import os
import secrets
from collections.abc import Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


ACCESS_CODE_HEADER = "X-Access-Code"

# Probes and public docs stay open when the gate is enabled.
_OPEN_PATHS = frozenset(
    {
        "/api/health",
        "/api/health/openai",
        "/api/health/catalogue",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


def required_access_codes() -> list[str] | None:
    """Parse MEAL_AGENT_ACCESS_CODE as a comma-separated allow-list."""
    raw = os.environ.get("MEAL_AGENT_ACCESS_CODE", "").strip()
    if not raw:
        return None
    codes = [part.strip() for part in raw.split(",") if part.strip()]
    return codes or None


# Back-compat alias used by older call sites / docs.
def required_access_code() -> str | None:
    codes = required_access_codes()
    if not codes:
        return None
    return codes[0]


def access_code_ok(provided: str | None, expected: str | Sequence[str]) -> bool:
    if not provided:
        return False
    provided = provided.strip()
    expected_codes = [expected] if isinstance(expected, str) else list(expected)
    if not expected_codes:
        return False

    matched = False
    for code in expected_codes:
        # compare_digest requires equal length; keep scanning all codes.
        if len(provided) == len(code) and secrets.compare_digest(provided, code):
            matched = True
    return matched


class AccessCodeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        expected = required_access_codes()
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
