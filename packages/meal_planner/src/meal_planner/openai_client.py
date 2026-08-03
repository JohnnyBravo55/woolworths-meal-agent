"""Shared AsyncOpenAI client for meal planning — connection reuse, bounded retries."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from meal_planner.openai_env import openai_api_key_from_env

# Cap completion size so a week of recipes cannot stream forever.
DEFAULT_MAX_TOKENS = 8192
# Per-attempt wall clock (streaming). One automatic retry may follow.
DEFAULT_TIMEOUT_SECONDS = 60.0

ProgressCallback = Callable[[int], Awaitable[None] | None]

_client: Any = None
_client_key: str | None = None


def reset_openai_client_for_tests() -> None:
    global _client, _client_key
    _client = None
    _client_key = None


def get_async_openai(*, api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS):
    """Return a process-wide AsyncOpenAI client (recreated if the key changes)."""
    global _client, _client_key
    from openai import AsyncOpenAI

    key = (api_key if api_key is not None else openai_api_key_from_env()).strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if _client is None or _client_key != key:
        _client = AsyncOpenAI(
            api_key=key,
            timeout=timeout,
            # Default SDK retries (2) can sit silent for a long time on 429/network.
            max_retries=1,
        )
        _client_key = key
    return _client


async def stream_chat_json(
    *,
    model: str,
    system: str,
    user: str,
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.7,
    on_progress: ProgressCallback | None = None,
) -> str:
    """Stream a JSON-object chat completion; return the full content string.

    Streaming keeps bytes flowing (Cloudflare/Render) and lets the API surface
    progress while OpenAI is still generating — not only after it finishes.
    """
    client = get_async_openai(api_key=api_key, timeout=timeout)

    async def _consume() -> str:
        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        parts: list[str] = []
        async for event in stream:
            choices = getattr(event, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            piece = getattr(delta, "content", None) if delta is not None else None
            if not piece:
                continue
            parts.append(piece)
            if on_progress is not None:
                maybe = on_progress(sum(len(p) for p in parts))
                if maybe is not None:
                    await maybe
        return "".join(parts)

    try:
        return await asyncio.wait_for(_consume(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"OpenAI meal planning timed out after {int(timeout)}s"
        ) from exc
