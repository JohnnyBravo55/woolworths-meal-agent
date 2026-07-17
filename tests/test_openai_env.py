"""OpenAI env sanitization and secret redaction."""

from meal_planner.openai_env import redact_secrets, sanitize_openai_api_key


def test_sanitize_strips_multiline_env_paste():
    raw = "sk-proj-abc123\nOPENAI_MODEL=gpt-4o-mini"
    assert sanitize_openai_api_key(raw) == "sk-proj-abc123"


def test_sanitize_strips_quotes_and_prefix():
    assert sanitize_openai_api_key('  "sk-test"  ') == "sk-test"
    assert sanitize_openai_api_key("OPENAI_API_KEY=sk-test") == "sk-test"


def test_redact_secrets_masks_bearer_and_sk():
    text = "Illegal header value b'Bearer sk-proj-EXAMPLEKEYVALUE000000000000000000000000'"
    out = redact_secrets(text)
    assert "EXAMPLEKEYVALUE" not in out
    assert "Bearer [REDACTED]" in out or "sk-[REDACTED]" in out
