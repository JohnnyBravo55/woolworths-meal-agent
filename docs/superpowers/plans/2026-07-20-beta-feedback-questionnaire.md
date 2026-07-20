# Beta Feedback Questionnaire Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a short end-of-flow feedback questionnaire on the hosted cart “coming soon” page that posts answers through the API into the existing Google Sheet (`Feedback` + `Summary` tabs).

**Architecture:** Mirror the NDA path: Expo web UI → `POST /api/feedback/submit` → local JSON mirror → Google Apps Script webhook (same `NDA_SHEETS_*` env) → Sheet tabs. Apps Script routes by `type: "feedback"` vs NDA (default).

**Tech Stack:** FastAPI, Pydantic, httpx, Expo / React Native Web, Google Apps Script, pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-beta-feedback-questionnaire-design.md`

## Global Constraints

- Same Google Sheet as NDA; tabs `Feedback` and `Summary`
- Reuse `NDA_SHEETS_WEBHOOK_URL` + `NDA_SHEETS_SECRET` (never expose to frontend)
- Exact option strings from the spec (stable for `COUNTIF`)
- Hosted cart coming-soon only (`Platform.OS === "web"` path via `HostedCartComingSoon`); native trolley flow out of scope
- Auto-open after 10s; skip if `localStorage` `meal-agent-feedback-submitted=1`; dismiss uses `sessionStorage` for that visit
- When Sheets env unset (local): accept + mirror JSON only; when set: hard-fail submit on Sheets error (503), same as NDA

---

## File structure

| File | Responsibility |
|------|----------------|
| `apps/api/src/meal_agent_api/feedback.py` | Option enums, `FeedbackSubmission` dataclass, JSON store, Sheets append |
| `apps/api/src/meal_agent_api/schemas.py` | `FeedbackSubmitRequest` |
| `apps/api/src/meal_agent_api/main.py` | `POST /api/feedback/submit` |
| `tests/test_feedback_submit.py` | API + webhook tests |
| `docs/nda-google-sheets-apps-script.js` | Route `type===feedback`, append + seed Summary |
| `packages/app-core/src/api/client.ts` | `submitFeedback(...)` |
| `apps/mobile/constants/feedback.ts` | Questions, options, storage keys |
| `apps/mobile/components/FeedbackModal.tsx` | Scrollable chip form + submit |
| `apps/mobile/components/HostedCartComingSoon.tsx` | Feedback button + 10s auto-open |
| `README.md` | Setup note for Feedback / Summary tabs |

---

### Task 1: Feedback store + Sheets append (API core)

**Files:**
- Create: `apps/api/src/meal_agent_api/feedback.py`
- Test: `tests/test_feedback_submit.py`

**Interfaces:**
- Produces:
  - `MEAL_PLAN_USEFUL_OPTIONS`, `MOST_VALUABLE_OPTIONS`, `LIKELIHOOD_OPTIONS`, `IF_NEVER_PUBLIC_OPTIONS` (tuples of exact strings)
  - `FeedbackSubmission` dataclass
  - `FeedbackStore.append(...) -> FeedbackSubmission`
  - `feedback_store: FeedbackStore`
  - `append_feedback_to_sheet(record: FeedbackSubmission) -> None` (no-op if webhook env unset; raises on HTTP/`ok:false` when configured)
  - `sheets_configured() -> bool`

- [ ] **Step 1: Write the failing webhook test**

Create `tests/test_feedback_submit.py`:

```python
"""Feedback submit endpoint + Google Sheets webhook."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_agent_api.feedback import FeedbackSubmission, append_feedback_to_sheet
from meal_agent_api.main import app


VALID_BODY = {
    "meal_plan_useful": "Useful",
    "most_valuable": "Shopping list",
    "use_again": "Likely",
    "if_never_public": "Disappointed",
    "premium_subscribe": "Very likely",
    "improve": "Faster plan generation",
    "session_id": "sess-1",
}


@pytest.fixture()
def feedback_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from meal_agent_api.feedback import FeedbackStore

    path = tmp_path / "feedback_submissions.json"
    store = FeedbackStore(path)
    monkeypatch.setattr("meal_agent_api.main.feedback_store", store)
    monkeypatch.setattr("meal_agent_api.feedback.feedback_store", store)
    return path


def test_append_feedback_to_sheet_noop_without_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NDA_SHEETS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NDA_SHEETS_SECRET", raising=False)
    calls: list = []
    monkeypatch.setattr("meal_agent_api.feedback.httpx.post", lambda *a, **k: calls.append(1))
    append_feedback_to_sheet(
        FeedbackSubmission(
            id="abc",
            submitted_at="2026-07-20T00:00:00+00:00",
            session_id="s1",
            meal_plan_useful="Useful",
            most_valuable="Shopping list",
            use_again="Likely",
            if_never_public="Disappointed",
            premium_subscribe="Very likely",
            improve="",
            user_agent="pytest",
        )
    )
    assert calls == []


def test_append_feedback_to_sheet_posts_webhook(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NDA_SHEETS_WEBHOOK_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("NDA_SHEETS_SECRET", "test-secret")
    calls: list[dict] = []

    class FakeResponse:
        status_code = 200
        text = '{"ok":true}'

        def json(self):
            return {"ok": True}

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("meal_agent_api.feedback.httpx.post", fake_post)
    append_feedback_to_sheet(
        FeedbackSubmission(
            id="abc",
            submitted_at="2026-07-20T00:00:00+00:00",
            session_id="s1",
            meal_plan_useful="Useful",
            most_valuable="Shopping list",
            use_again="Likely",
            if_never_public="Disappointed",
            premium_subscribe="Very likely",
            improve="note",
            user_agent="pytest",
        )
    )
    assert calls[0]["json"]["type"] == "feedback"
    assert calls[0]["json"]["secret"] == "test-secret"
    assert calls[0]["json"]["meal_plan_useful"] == "Useful"
    assert calls[0]["json"]["premium_subscribe"] == "Very likely"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_feedback_submit.py::test_append_feedback_to_sheet_noop_without_env tests/test_feedback_submit.py::test_append_feedback_to_sheet_posts_webhook -v`

Expected: FAIL with `ModuleNotFoundError` or import error for `meal_agent_api.feedback`

- [ ] **Step 3: Implement `feedback.py`**

Create `apps/api/src/meal_agent_api/feedback.py`:

```python
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
```

Note: confirm `PROJECT_ROOT` depth matches `nda.py` (`Path(__file__).resolve().parents[4]` — same as NDA module).

- [ ] **Step 4: Run webhook tests**

Run: `pytest tests/test_feedback_submit.py::test_append_feedback_to_sheet_noop_without_env tests/test_feedback_submit.py::test_append_feedback_to_sheet_posts_webhook -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/meal_agent_api/feedback.py tests/test_feedback_submit.py
git commit -m "Add feedback store and Sheets webhook helper."
```

---

### Task 2: `POST /api/feedback/submit` endpoint

**Files:**
- Modify: `apps/api/src/meal_agent_api/schemas.py`
- Modify: `apps/api/src/meal_agent_api/main.py`
- Modify: `tests/test_feedback_submit.py`

**Interfaces:**
- Consumes: `feedback_store`, `append_feedback_to_sheet`, `sheets_configured`, option tuples from Task 1
- Produces: `POST /api/feedback/submit` → `{ ok, id, submitted_at }`

- [ ] **Step 1: Add failing endpoint tests** to `tests/test_feedback_submit.py`

```python
def test_feedback_submit_rejects_invalid_option(feedback_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    monkeypatch.delenv("NDA_SHEETS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NDA_SHEETS_SECRET", raising=False)
    client = TestClient(app)
    bad = {**VALID_BODY, "use_again": "Maybe"}
    res = client.post("/api/feedback/submit", json=bad)
    assert res.status_code == 422


def test_feedback_submit_stores_locally_without_sheets(
    feedback_file: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    monkeypatch.delenv("NDA_SHEETS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NDA_SHEETS_SECRET", raising=False)
    client = TestClient(app)
    res = client.post(
        "/api/feedback/submit",
        json=VALID_BODY,
        headers={"User-Agent": "pytest-agent"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["id"]
    assert body["submitted_at"]
    rows = json.loads(feedback_file.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["most_valuable"] == "Shopping list"
    assert rows[0]["user_agent"] == "pytest-agent"


def test_feedback_submit_sheet_failure_returns_503(
    feedback_file: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("MEAL_AGENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "")
    monkeypatch.setenv("NDA_SHEETS_WEBHOOK_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("NDA_SHEETS_SECRET", "test-secret")

    def boom(_record) -> None:
        raise RuntimeError("Sheets down")

    monkeypatch.setattr("meal_agent_api.main.append_feedback_to_sheet", boom)
    client = TestClient(app)
    res = client.post("/api/feedback/submit", json=VALID_BODY)
    assert res.status_code == 503
    rows = json.loads(feedback_file.read_text(encoding="utf-8"))
    assert len(rows) == 1


def test_feedback_submit_gated_by_access_code(
    feedback_file: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("MEAL_AGENT_ACCESS_CODE", "usertest1")
    monkeypatch.delenv("NDA_SHEETS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NDA_SHEETS_SECRET", raising=False)
    client = TestClient(app)
    denied = client.post("/api/feedback/submit", json=VALID_BODY)
    assert denied.status_code == 401
    ok = client.post(
        "/api/feedback/submit",
        headers={"X-Access-Code": "usertest1"},
        json=VALID_BODY,
    )
    assert ok.status_code == 200
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_feedback_submit.py -v`

Expected: FAIL on endpoint tests (404) while webhook tests still PASS

- [ ] **Step 3: Add schema**

In `apps/api/src/meal_agent_api/schemas.py`, after `NdaAcceptRequest`:

```python
class FeedbackSubmitRequest(BaseModel):
    meal_plan_useful: str
    most_valuable: str
    use_again: str
    if_never_public: str
    premium_subscribe: str
    improve: str = ""
    session_id: str = ""
```

- [ ] **Step 4: Wire endpoint in `main.py`**

Import:

```python
from meal_agent_api.feedback import (
    IF_NEVER_PUBLIC_OPTIONS,
    LIKELIHOOD_OPTIONS,
    MEAL_PLAN_USEFUL_OPTIONS,
    MOST_VALUABLE_OPTIONS,
    append_feedback_to_sheet,
    feedback_store,
    sheets_configured,
)
from meal_agent_api.schemas import FeedbackSubmitRequest  # add to existing schemas import
```

Add after NDA section:

```python
# --- Feedback (hosted beta testers) ---


@app.post("/api/feedback/submit")
async def feedback_submit(body: FeedbackSubmitRequest, request: Request):
    checks = [
        (body.meal_plan_useful, MEAL_PLAN_USEFUL_OPTIONS, "meal_plan_useful"),
        (body.most_valuable, MOST_VALUABLE_OPTIONS, "most_valuable"),
        (body.use_again, LIKELIHOOD_OPTIONS, "use_again"),
        (body.if_never_public, IF_NEVER_PUBLIC_OPTIONS, "if_never_public"),
        (body.premium_subscribe, LIKELIHOOD_OPTIONS, "premium_subscribe"),
    ]
    for value, allowed, field in checks:
        if value not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {field}. Expected one of: {', '.join(allowed)}",
            )

    user_agent = request.headers.get("user-agent")
    record = feedback_store.append(
        session_id=body.session_id or "",
        meal_plan_useful=body.meal_plan_useful,
        most_valuable=body.most_valuable,
        use_again=body.use_again,
        if_never_public=body.if_never_public,
        premium_subscribe=body.premium_subscribe,
        improve=body.improve or "",
        user_agent=user_agent,
    )
    if sheets_configured():
        try:
            append_feedback_to_sheet(record)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Feedback could not be saved to the owner spreadsheet. "
                    f"Record id: {record.id}. Please try again or contact the owner."
                ),
            ) from exc
    else:
        # Local/dev without Sheets: still persist JSON mirror.
        append_feedback_to_sheet(record)  # no-op

    return {"ok": True, "id": record.id, "submitted_at": record.submitted_at}
```

Simplify the else branch to just skip (do not call no-op explicitly if clearer):

```python
    if sheets_configured():
        try:
            append_feedback_to_sheet(record)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Feedback could not be saved to the owner spreadsheet. "
                    f"Record id: {record.id}. Please try again or contact the owner."
                ),
            ) from exc

    return {"ok": True, "id": record.id, "submitted_at": record.submitted_at}
```

- [ ] **Step 5: Run all feedback tests**

Run: `pytest tests/test_feedback_submit.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/meal_agent_api/schemas.py apps/api/src/meal_agent_api/main.py tests/test_feedback_submit.py
git commit -m "Add POST /api/feedback/submit for beta questionnaire."
```

---

### Task 3: Extend Apps Script + README

**Files:**
- Modify: `docs/nda-google-sheets-apps-script.js`
- Modify: `README.md` (NDA → Google Sheet section)

**Interfaces:**
- Consumes: webhook JSON with `type: "feedback"` from Task 1
- Produces: rows on `Feedback`; `Summary` tab with COUNTIF formulas

- [ ] **Step 1: Replace Apps Script with typed router**

Rewrite `docs/nda-google-sheets-apps-script.js` to:

```javascript
/**
 * Meal Agent — NDA acceptances + beta feedback → Google Sheet
 *
 * Setup:
 * 1. Create a Google Sheet (or reuse the NDA sheet).
 * 2. Extensions → Apps Script → paste this file → Save.
 * 3. Project Settings → Script properties → NDA_SECRET = <same as Render NDA_SHEETS_SECRET>
 * 4. Deploy → Web app → Execute as: Me; Who has access: Anyone.
 * 5. Render: NDA_SHEETS_WEBHOOK_URL + NDA_SHEETS_SECRET
 * 6. After edits: Deploy → Manage deployments → Edit → New version.
 *
 * Tabs:
 * - Acceptances (NDA)
 * - Feedback (questionnaire rows)
 * - Summary (auto tallies from Feedback)
 */

function doPost(e) {
  var expected = PropertiesService.getScriptProperties().getProperty("NDA_SECRET");
  if (!expected) {
    return jsonOut_({ ok: false, error: "NDA_SECRET not configured in Script properties" });
  }

  var body;
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || "{}");
  } catch (err) {
    return jsonOut_({ ok: false, error: "Invalid JSON" });
  }

  if (!body.secret || body.secret !== expected) {
    return jsonOut_({ ok: false, error: "Unauthorized" });
  }

  var type = String(body.type || "nda").toLowerCase();
  if (type === "feedback") {
    return handleFeedback_(body);
  }
  return handleNda_(body);
}

function handleNda_(body) {
  var name = String(body.full_name || "").trim();
  if (!name) {
    return jsonOut_({ ok: false, error: "full_name required" });
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Acceptances") || ss.getSheets()[0];
  sheet.appendRow([
    body.accepted_at || new Date().toISOString(),
    name,
    body.nda_version || "",
    body.id || "",
    body.client_ip || "",
    body.user_agent || "",
  ]);

  return jsonOut_({ ok: true });
}

function handleFeedback_(body) {
  var required = [
    "meal_plan_useful",
    "most_valuable",
    "use_again",
    "if_never_public",
    "premium_subscribe",
  ];
  for (var i = 0; i < required.length; i++) {
    if (!String(body[required[i]] || "").trim()) {
      return jsonOut_({ ok: false, error: required[i] + " required" });
    }
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Feedback");
  if (!sheet) {
    sheet = ss.insertSheet("Feedback");
  }
  ensureFeedbackHeader_(sheet);
  ensureSummarySheet_(ss);

  sheet.appendRow([
    body.submitted_at || new Date().toISOString(),
    body.id || "",
    body.session_id || "",
    body.meal_plan_useful || "",
    body.most_valuable || "",
    body.use_again || "",
    body.if_never_public || "",
    body.premium_subscribe || "",
    body.improve || "",
    body.user_agent || "",
  ]);

  return jsonOut_({ ok: true });
}

function ensureFeedbackHeader_(sheet) {
  if (sheet.getLastRow() > 0) return;
  sheet.appendRow([
    "submitted_at",
    "id",
    "session_id",
    "meal_plan_useful",
    "most_valuable",
    "use_again",
    "if_never_public",
    "premium_subscribe",
    "improve",
    "user_agent",
  ]);
}

function ensureSummarySheet_(ss) {
  var sheet = ss.getSheetByName("Summary");
  if (sheet && sheet.getRange("A1").getValue() === "Metric") return;
  if (!sheet) sheet = ss.insertSheet("Summary");
  sheet.clear();

  var rows = [
    ["Metric", "Value"],
    ["Total responses", "=COUNTA(Feedback!A:A)-1"],
    [],
    ["Use again — Very likely", '=COUNTIF(Feedback!F:F,"Very likely")'],
    ["Use again — Likely", '=COUNTIF(Feedback!F:F,"Likely")'],
    ["Use again — Unsure", '=COUNTIF(Feedback!F:F,"Unsure")'],
    ["Use again — Unlikely", '=COUNTIF(Feedback!F:F,"Unlikely")'],
    ["Use again — Definitely not", '=COUNTIF(Feedback!F:F,"Definitely not")'],
    ["Use again positive %", '=IF(B2<=0,"", (B4+B5)/B2)'],
    [],
    ["Never public — Very disappointed", '=COUNTIF(Feedback!G:G,"Very disappointed")'],
    ["Never public — Disappointed", '=COUNTIF(Feedback!G:G,"Disappointed")'],
    ["Never public — Unsure", '=COUNTIF(Feedback!G:G,"Unsure")'],
    ["Never public — Not disappointed", '=COUNTIF(Feedback!G:G,"Not disappointed")'],
    ["Never public — Not at all disappointed", '=COUNTIF(Feedback!G:G,"Not at all disappointed")'],
    ["Disappointed if never public %", '=IF(B2<=0,"", (B11+B12)/B2)'],
    [],
    ["Premium — Very likely", '=COUNTIF(Feedback!H:H,"Very likely")'],
    ["Premium — Likely", '=COUNTIF(Feedback!H:H,"Likely")'],
    ["Premium — Unsure", '=COUNTIF(Feedback!H:H,"Unsure")'],
    ["Premium — Unlikely", '=COUNTIF(Feedback!H:H,"Unlikely")'],
    ["Premium — Definitely not", '=COUNTIF(Feedback!H:H,"Definitely not")'],
    ["Premium interest % (NZ$9.99)", '=IF(B2<=0,"", (B18+B19)/B2)'],
    [],
    ["Most valuable — Chef meal plan", '=COUNTIF(Feedback!E:E,"Chef meal plan")'],
    ["Most valuable — Shopping list", '=COUNTIF(Feedback!E:E,"Shopping list")'],
    ["Most valuable — Personalised preferences", '=COUNTIF(Feedback!E:E,"Personalised preferences")'],
    ["Most valuable — Saving time", '=COUNTIF(Feedback!E:E,"Saving time")'],
    ["Most valuable — None", '=COUNTIF(Feedback!E:E,"None")'],
    [],
    ["Meal plan — Very useful", '=COUNTIF(Feedback!D:D,"Very useful")'],
    ["Meal plan — Useful", '=COUNTIF(Feedback!D:D,"Useful")'],
    ["Meal plan — Unsure", '=COUNTIF(Feedback!D:D,"Unsure")'],
    ["Meal plan — Unhelpful", '=COUNTIF(Feedback!D:D,"Unhelpful")'],
    ["Meal plan — Not useful", '=COUNTIF(Feedback!D:D,"Not useful")'],
  ];

  sheet.getRange(1, 1, rows.length, 2).setValues(
    rows.map(function (r) {
      return [r[0] || "", r[1] || ""];
    })
  );
  sheet.getRange("B9").setNumberFormat("0.0%");
  sheet.getRange("B16").setNumberFormat("0.0%");
  sheet.getRange("B23").setNumberFormat("0.0%");
}

function doGet() {
  return jsonOut_({ ok: true, service: "meal-agent-nda-feedback" });
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
```

- [ ] **Step 2: Update README §1b**

After the Acceptances header list, add:

```markdown
7. Feedback uses the **same** webhook. After pasting the updated Apps Script and redeploying a new version, the first feedback submit creates `Feedback` + `Summary` tabs (or create empty tabs manually). Open **Summary** for investor tallies (% use-again, disappointed-if-never-public, Premium at NZ$9.99).
```

Also extend tester instructions step after cart coming soon:

```markdown
7. On the cart “coming soon” page, tap **Feedback** (or wait 10 seconds) and submit the short questionnaire — answers land on the owner’s Sheet `Feedback` tab.
```

- [ ] **Step 3: Commit**

```bash
git add docs/nda-google-sheets-apps-script.js README.md
git commit -m "Route feedback submissions into Sheet Feedback and Summary tabs."
```

Manual owner step (not automated): paste script into Apps Script → New version deploy.

---

### Task 4: App-core `submitFeedback` client

**Files:**
- Modify: `packages/app-core/src/api/client.ts`

**Interfaces:**
- Consumes: `POST /api/feedback/submit`
- Produces: `api.submitFeedback(opts) -> { ok, id, submitted_at }`

- [ ] **Step 1: Add method next to `acceptNda`**

```typescript
    submitFeedback: (opts: {
      meal_plan_useful: string;
      most_valuable: string;
      use_again: string;
      if_never_public: string;
      premium_subscribe: string;
      improve?: string;
      session_id?: string;
    }) =>
      jsonFetch<{
        ok: boolean;
        id: string;
        submitted_at: string;
      }>("/api/feedback/submit", {
        method: "POST",
        body: JSON.stringify({
          meal_plan_useful: opts.meal_plan_useful,
          most_valuable: opts.most_valuable,
          use_again: opts.use_again,
          if_never_public: opts.if_never_public,
          premium_subscribe: opts.premium_subscribe,
          improve: opts.improve ?? "",
          session_id: opts.session_id ?? "",
        }),
      }),
```

- [ ] **Step 2: Commit**

```bash
git add packages/app-core/src/api/client.ts
git commit -m "Add app-core submitFeedback API client method."
```

---

### Task 5: Feedback constants + modal UI

**Files:**
- Create: `apps/mobile/constants/feedback.ts`
- Create: `apps/mobile/components/FeedbackModal.tsx`

**Interfaces:**
- Consumes: `api.submitFeedback`, session id from session store / `api` caller
- Produces: `FeedbackModal` props `{ visible, onClose, onSubmitted }`

- [ ] **Step 1: Create `apps/mobile/constants/feedback.ts`**

```typescript
export const FEEDBACK_SUBMITTED_KEY = "meal-agent-feedback-submitted";
export const FEEDBACK_DISMISSED_VISIT_KEY = "meal-agent-feedback-dismissed-visit";
export const FEEDBACK_AUTO_OPEN_MS = 10_000;

export const MEAL_PLAN_USEFUL_OPTIONS = [
  "Very useful",
  "Useful",
  "Unsure",
  "Unhelpful",
  "Not useful",
] as const;

export const MOST_VALUABLE_OPTIONS = [
  "Chef meal plan",
  "Shopping list",
  "Personalised preferences",
  "Saving time",
  "None",
] as const;

export const LIKELIHOOD_OPTIONS = [
  "Very likely",
  "Likely",
  "Unsure",
  "Unlikely",
  "Definitely not",
] as const;

export const IF_NEVER_PUBLIC_OPTIONS = [
  "Very disappointed",
  "Disappointed",
  "Unsure",
  "Not disappointed",
  "Not at all disappointed",
] as const;

export type MealPlanUseful = (typeof MEAL_PLAN_USEFUL_OPTIONS)[number];
export type MostValuable = (typeof MOST_VALUABLE_OPTIONS)[number];
export type Likelihood = (typeof LIKELIHOOD_OPTIONS)[number];
export type IfNeverPublic = (typeof IF_NEVER_PUBLIC_OPTIONS)[number];
```

- [ ] **Step 2: Create `FeedbackModal.tsx`**

Implement a transparent `Modal` (pattern from `LoadingOverlay.tsx`) with:

- Title: “Quick feedback”
- Subtitle: “Helps us improve Meal Agent — about 30 seconds”
- Five chip groups (Pressable pills) for Q1–Q5 using constants above
- Optional `TextInput` multiline for improve (maxLength 1000)
- Primary **Submit** (`Button`) disabled until all five answers set; shows loading while posting
- Ghost **Not now** / close → `onClose()`
- On success: set thank-you text, call `onSubmitted()`, then close after short delay or show Done button
- Call `api.submitFeedback({...})` from `@/lib/api`
- Pass `session_id` from `await` session store if easily available via existing `api` helpers; otherwise omit (header already sends `X-Session-Id`)

Chip styling: selected = `theme.primary` background / white text; unselected = muted border. Keep layout compact for mobile web.

Skeleton:

```tsx
import { useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Button } from "@/components/ui/Button";
import { theme } from "@/constants/theme";
import {
  FEEDBACK_SUBMITTED_KEY,
  IF_NEVER_PUBLIC_OPTIONS,
  LIKELIHOOD_OPTIONS,
  MEAL_PLAN_USEFUL_OPTIONS,
  MOST_VALUABLE_OPTIONS,
  type IfNeverPublic,
  type Likelihood,
  type MealPlanUseful,
  type MostValuable,
} from "@/constants/feedback";
import { api } from "@/lib/api";

type Props = {
  visible: boolean;
  onClose: () => void;
  onSubmitted: () => void;
};

export function FeedbackModal({ visible, onClose, onSubmitted }: Props) {
  // state for each answer + improve + loading + error + thanks
  // submit handler calls api.submitFeedback then localStorage.setItem(FEEDBACK_SUBMITTED_KEY, "1")
  // ...
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/mobile/constants/feedback.ts apps/mobile/components/FeedbackModal.tsx
git commit -m "Add feedback questionnaire modal and option constants."
```

---

### Task 6: Wire button + 10s auto-open on hosted cart

**Files:**
- Modify: `apps/mobile/components/HostedCartComingSoon.tsx`

**Interfaces:**
- Consumes: `FeedbackModal`, storage keys, `FEEDBACK_AUTO_OPEN_MS`

- [ ] **Step 1: Update `HostedCartComingSoon`**

```tsx
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { FeedbackModal } from "@/components/FeedbackModal";
import { Button } from "@/components/ui/Button";
import {
  FEEDBACK_AUTO_OPEN_MS,
  FEEDBACK_DISMISSED_VISIT_KEY,
  FEEDBACK_SUBMITTED_KEY,
} from "@/constants/feedback";
import { theme } from "@/constants/theme";

// ... existing RETAILERS ...

function readStorage(storage: Storage | undefined, key: string): boolean {
  try {
    return storage?.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeStorage(storage: Storage | undefined, key: string): void {
  try {
    storage?.setItem(key, "1");
  } catch {
    /* ignore */
  }
}

export function HostedCartComingSoon() {
  const [toast, setToast] = useState("");
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (readStorage(window.localStorage, FEEDBACK_SUBMITTED_KEY)) return;
    if (readStorage(window.sessionStorage, FEEDBACK_DISMISSED_VISIT_KEY)) return;
    const t = setTimeout(() => setFeedbackOpen(true), FEEDBACK_AUTO_OPEN_MS);
    return () => clearTimeout(t);
  }, []);

  const closeFeedback = () => {
    setFeedbackOpen(false);
    if (typeof window !== "undefined") {
      writeStorage(window.sessionStorage, FEEDBACK_DISMISSED_VISIT_KEY);
    }
  };

  const onSubmitted = () => {
    setFeedbackOpen(false);
    if (typeof window !== "undefined") {
      writeStorage(window.localStorage, FEEDBACK_SUBMITTED_KEY);
    }
  };

  return (
    <View style={styles.wrap}>
      {/* existing title, subtitle, retailer buttons, toast */}

      <Button title="Feedback" onPress={() => setFeedbackOpen(true)} />

      <FeedbackModal
        visible={feedbackOpen}
        onClose={closeFeedback}
        onSubmitted={onSubmitted}
      />
    </View>
  );
}
```

Place the **Feedback** button below the retailer list (above toast). Keep retailer teaser behaviour unchanged.

- [ ] **Step 2: Manual smoke (local)**

1. `MEAL_AGENT_DEV_PREMIUM=1` / access code unset locally if needed; start API.
2. Open Expo web cart coming-soon path (or jump to `/cart` after a short flow).
3. Confirm Feedback button opens modal; wait 10s for auto-open on fresh storage.
4. Submit → `data/feedback_submissions.json` gains a row when Sheets env unset.
5. Dismiss without submit → no second auto-open that visit; button still works.

- [ ] **Step 3: Commit**

```bash
git add apps/mobile/components/HostedCartComingSoon.tsx
git commit -m "Auto-open feedback on hosted cart coming-soon page."
```

---

### Task 7: Final verification + deploy notes

**Files:**
- Touch only if tests/docs need fixes from Task 6 smoke

- [ ] **Step 1: Run API tests**

Run: `pytest tests/test_feedback_submit.py tests/test_nda_accept.py -v`

Expected: all PASS (NDA path unchanged)

- [ ] **Step 2: Owner checklist (document in commit message / chat)**

1. Paste updated `docs/nda-google-sheets-apps-script.js` into Apps Script → Save  
2. Deploy → Manage deployments → New version  
3. Confirm Render still has `NDA_SHEETS_WEBHOOK_URL` + `NDA_SHEETS_SECRET`  
4. Redeploy/restart API if code not yet live  
5. Submit one test feedback from hosted site; confirm `Feedback` row + `Summary` counts  

- [ ] **Step 3: Final commit if any leftover doc tweaks**

```bash
git add -A
git status
# commit only if there are intentional leftover changes
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Q1–Q6 copy + exact options | 1, 5 |
| `POST /api/feedback/submit` + validation | 2 |
| Local JSON mirror when Sheets unset | 1–2 |
| Sheets fail → 503 when configured | 2 |
| Same webhook env / `type: feedback` | 1, 3 |
| `Feedback` + `Summary` tabs | 3 |
| Feedback button on coming soon | 6 |
| 10s auto-open | 6 |
| localStorage submitted / sessionStorage dismiss | 5–6 |
| app-core client | 4 |
| README / redeploy notes | 3, 7 |
| Native trolley out of scope | (no task) |

## Self-review notes

- No TBD placeholders left in tasks.
- Option strings duplicated in Python + TS by design (keep in sync with spec).
- NDA Apps Script remains backward compatible when `type` omitted.
- Summary formula row numbers in Apps Script must match the `rows` array layout above — do not reorder metrics without updating `%` cell refs (`B9`, `B16`, `B23`).
