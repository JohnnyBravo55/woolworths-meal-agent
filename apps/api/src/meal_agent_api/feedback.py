"""Beta feedback store + Google Sheets webhook (same Apps Script as NDA)."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import httpx

from meal_agent_api.nda import sheets_secret, sheets_webhook_url

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FEEDBACK_FILE = PROJECT_ROOT / "data" / "feedback_submissions.json"

MEAL_PLAN_USEFUL_OPTIONS = (
    "Very useful",
    "Useful",
    "Unsure",
    "Unhelpful",
    "Not useful",
)
MOST_VALUABLE_OPTIONS = (
    "Chef meal plan",
    "Shopping list",
    "Personalised preferences",
    "Saving time",
    "None",
)
LIKELIHOOD_OPTIONS = (
    "Very likely",
    "Likely",
    "Unsure",
    "Unlikely",
    "Definitely not",
)
IF_NEVER_PUBLIC_OPTIONS = (
    "Very disappointed",
    "Disappointed",
    "Unsure",
    "Not disappointed",
    "Not at all disappointed",
)


@dataclass
class FeedbackSubmission:
    id: str
    submitted_at: str
    session_id: str
    meal_plan_useful: str
    most_valuable: str
    use_again: str
    if_never_public: str
    premium_subscribe: str
    improve: str = ""
    user_agent: str | None = None


class FeedbackStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or FEEDBACK_FILE
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        raw = self._path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, list) else []

    def _save(self, rows: list[dict]) -> None:
        self._path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def append(
        self,
        *,
        session_id: str,
        meal_plan_useful: str,
        most_valuable: str,
        use_again: str,
        if_never_public: str,
        premium_subscribe: str,
        improve: str = "",
        user_agent: str | None = None,
    ) -> FeedbackSubmission:
        record = FeedbackSubmission(
            id=str(uuid.uuid4()),
            submitted_at=datetime.now(timezone.utc).isoformat(),
            session_id=(session_id or "").strip(),
            meal_plan_useful=meal_plan_useful,
            most_valuable=most_valuable,
            use_again=use_again,
            if_never_public=if_never_public,
            premium_subscribe=premium_subscribe,
            improve=(improve or "")[:1000],
            user_agent=user_agent,
        )
        with self._lock:
            rows = self._load()
            rows.append(asdict(record))
            self._save(rows)
        return record


feedback_store = FeedbackStore()


def sheets_configured() -> bool:
    return bool(sheets_webhook_url() and sheets_secret())


def append_feedback_to_sheet(record: FeedbackSubmission) -> None:
    """Append feedback to Google Sheet via Apps Script. No-op if env unset."""
    url = sheets_webhook_url()
    secret = sheets_secret()
    if not url or not secret:
        return

    response = httpx.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "type": "feedback",
            "secret": secret,
            "id": record.id,
            "submitted_at": record.submitted_at,
            "session_id": record.session_id,
            "meal_plan_useful": record.meal_plan_useful,
            "most_valuable": record.most_valuable,
            "use_again": record.use_again,
            "if_never_public": record.if_never_public,
            "premium_subscribe": record.premium_subscribe,
            "improve": record.improve or "",
            "user_agent": record.user_agent or "",
        },
        timeout=30.0,
        follow_redirects=True,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Google Sheets webhook failed ({response.status_code}): {response.text[:500]}"
        )
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise RuntimeError(
            f"Google Sheets webhook rejected the request: {response.text[:500]}"
        )
