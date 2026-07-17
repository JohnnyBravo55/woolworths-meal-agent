"""Sanitize OpenAI env values and redact secrets from error text."""

from __future__ import annotations

import os
import re

_BEARER_RE = re.compile(r"(Bearer\s+)(\S+)", re.IGNORECASE)
_SK_RE = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,})\b")


def sanitize_openai_api_key(raw: str | None) -> str:
    """Normalize an API key from env / paste mistakes.

    Render (and .env) pastes sometimes glue the next variable into the value:
    ``sk-...\\nOPENAI_MODEL=gpt-4o-mini``. HTTP forbids newlines in headers.
    """
    if not raw:
        return ""
    first = raw.strip().splitlines()[0].strip()
    if len(first) >= 2 and first[0] == first[-1] and first[0] in {'"', "'"}:
        first = first[1:-1].strip()
    if first.upper().startswith("OPENAI_API_KEY="):
        first = first.split("=", 1)[1].strip()
    return first


def openai_api_key_from_env() -> str:
    return sanitize_openai_api_key(os.environ.get("OPENAI_API_KEY"))


def redact_secrets(text: str) -> str:
    """Remove API keys from diagnostic / user-facing error strings."""
    if not text:
        return text
    redacted = _BEARER_RE.sub(r"\1[REDACTED]", text)
    return _SK_RE.sub("sk-[REDACTED]", redacted)
