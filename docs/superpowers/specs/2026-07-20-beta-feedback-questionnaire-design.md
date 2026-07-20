# Beta feedback questionnaire → Google Sheet

**Date:** 2026-07-20  
**Status:** Approved for implementation

## Goal

Collect short, investor-relevant beta feedback at the end of the hosted tester flow (cart “coming soon” page), store each response in the owner’s Google Sheet in a form that is easy to tally, and keep secrets off the client.

## Decisions

| Topic | Choice |
|-------|--------|
| Placement | Hosted cart “Fill shopping cart, coming soon” screen (`HostedCartComingSoon` / Expo web cart step) |
| Entry | **Feedback** button always available; modal auto-opens after **10 seconds** on that page |
| After submit | Do not auto-open again; button can still reopen (read-only thank-you or empty submit disabled) |
| Dismiss | User can close without submitting; auto-open does not repeat that visit once dismissed or submitted (session/local flag) |
| Transport | Same pattern as NDA: mobile/web → API → Apps Script webhook → Sheet |
| Spreadsheet | **Same** Google Sheet as NDA acceptances; new tabs `Feedback` + `Summary` |
| Auth | Shared secret in Render env + Apps Script script property (never in frontend) |
| Scope | Hosted / Expo web cart coming-soon path first; native local trolley flow is out of scope for v1 |
| Apps Script | Extend the existing NDA web-app script (one deployment URL); route by `type` |)

## Questionnaire (locked)

All required except Q6. Prefer tap options.

### Q1 — Meal plan usefulness

**How useful was your meal plan?**

- Very useful  
- Useful  
- Unsure  
- Unhelpful  
- Not useful  

### Q2 — Most valuable part

**Which part was most valuable?**

- Chef meal plan  
- Shopping list  
- Personalised preferences  
- Saving time  
- None  

### Q3 — Use again

**How likely are you to use this app again?**

- Very likely  
- Likely  
- Unsure  
- Unlikely  
- Definitely not  

### Q4 — Public availability (PMF proxy)

**If Meal Agent never became publicly available, how would you feel?**

- Very disappointed  
- Disappointed  
- Unsure  
- Not disappointed  
- Not at all disappointed  

### Q5 — Premium WTP

**If Premium included specialised chefs and extra features for NZ$9.99/month, how likely are you to subscribe?**

- Very likely  
- Likely  
- Unsure  
- Unlikely  
- Definitely not  

### Q6 — Open improve (optional)

**Anything we could improve?**  
Free text, optional, max ~1000 characters.

## Architecture

```
Hosted cart page
  → Feedback modal (10s auto-open + button)
  → POST /api/feedback/submit
  → API validates + appends local mirror (optional JSON file)
  → POST Apps Script web app (secret + payload)
  → Google Sheet tab "Feedback" append row
  → "Summary" tab formulas count options
```

Reuse the existing NDA webhook env vars. Extend the Apps Script to route by `type`:

| Item | Detail |
|------|--------|
| Payload | `"type": "feedback"` for this feature; NDA keeps working when `type` is omitted or `"nda"` |
| Env | Keep `NDA_SHEETS_WEBHOOK_URL` + `NDA_SHEETS_SECRET` (same deployment URL/secret) |

## Sheet layout

### Tab: `Feedback` (raw rows)

Header row:

| Column | Field |
|--------|--------|
| A | `submitted_at` |
| B | `id` |
| C | `session_id` |
| D | `meal_plan_useful` |
| E | `most_valuable` |
| F | `use_again` |
| G | `if_never_public` |
| H | `premium_subscribe` |
| I | `improve` |
| J | `user_agent` (optional, for debugging) |

One append per successful submit. Exact option strings as shown above (stable for `COUNTIF`).

### Tab: `Summary` (auto tallies)

Pre-seeded formulas (implementation writes them once or documents copy-paste in Apps Script setup doc):

- Response count: `=COUNTA(Feedback!A:A)-1`
- For each of Q1, Q3, Q4, Q5: count and % for every option  
- For Q2: count and % per option  
- Investor-friendly rollups:
  - **Use again (positive):** Very likely + Likely  
  - **Disappointed if never public:** Very disappointed + Disappointed  
  - **Premium interest:** Very likely + Likely at NZ$9.99  

Owner opens `Summary` for investor updates; `Feedback` for raw comments.

## API

`POST /api/feedback/submit`

Request body (example):

```json
{
  "meal_plan_useful": "Useful",
  "most_valuable": "Shopping list",
  "use_again": "Likely",
  "if_never_public": "Disappointed",
  "premium_subscribe": "Very likely",
  "improve": "optional text",
  "session_id": "optional client session id"
}
```

Behaviour:

- Validate enums exactly against allowed option lists; reject unknowns with 422.
- Require Q1–Q5; `improve` optional.
- When Sheets webhook is configured, append to Sheet; fail the request if Sheets write fails (same hard failure model as NDA when webhook env is set).
- When webhook env is unset (local), accept and mirror to `data/feedback_submissions.json` so local/dev still works.
- Return `{ ok: true, id, submitted_at }`.

## Frontend (Expo web / hosted cart)

- On `HostedCartComingSoon` when shown on the cart step:
  - Render primary **Feedback** button.
  - After mount, start a 10s timer → open modal unless `localStorage` has `meal-agent-feedback-submitted=1`.
  - If the user dismisses without submitting, set a **sessionStorage** flag so auto-open does not fire again on that page visit; the Feedback button still works.
- Modal: single scrollable form with option chips (fastest on mobile web); Submit disabled until Q1–Q5 answered.
- On success: thank-you state; set `meal-agent-feedback-submitted=1`; stop future auto-open.
- Wire `api.submitFeedback(...)` in app-core client.

## Apps Script

Update [`docs/nda-google-sheets-apps-script.js`](../../nda-google-sheets-apps-script.js) in place (owner pastes into the same Apps Script project and redeploys a new version):

- If `body.type === "feedback"`: append to `Feedback` sheet; create the tab + header row if missing; ensure `Summary` tab exists with COUNTIF formulas (or document a one-time seed).
- Else: existing NDA `Acceptances` append (unchanged).
- Same `NDA_SECRET` / `body.secret` check.
- After editing: **Deploy → Manage deployments → Edit → New version**.

## Testing

- API unit/integration tests mirroring `tests/test_nda_accept.py`: validation, Sheets success/failure, local mirror when env unset.
- Frontend: optional light test that Feedback button renders on hosted cart component; timer behaviour can stay manual.

## Non-goals (v1)

- Price A/B testing ($7.99 / $12.99)
- Collecting email or full name on the feedback form (NDA already captured name separately)
- Showing the questionnaire on native local trolley-success flows
- Public analytics dashboards beyond the Sheet `Summary` tab

## Success criteria

- Hosted tester reaches cart coming-soon → Feedback appears (button + 10s auto).
- Submitted answers appear as one neat row on `Feedback` and update `Summary` counts.
- Secret never ships in the static frontend.
- Owner can paste Summary % into an investor update without manual spreadsheet pivot work.
