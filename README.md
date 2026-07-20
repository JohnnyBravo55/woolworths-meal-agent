# Woolworths NZ Meal Planning Agent

A conversational agent that collects dietary preferences and budget, builds simple chef-quality meal plans, maps ingredients to real Woolworths NZ products with live pricing, and adds them to your cart — with a fallback shopping list when automation is unavailable.

## Features

- Phased conversation: discovery → meal plan → approval → product resolution → budget check → cart
- Allergy hard-blocks and human approval before any cart writes
- Live Woolworths NZ product search and pricing via [woolies-nz-cli](https://github.com/mcinteerj/woolies-nz-cli)
- Budget engine with mandatory-items-first allocation and swap suggestions
- Markdown/CSV export fallback when cart automation fails
- Never auto-checkouts — stops at cart population
- **Cross-platform Expo app** (iOS, Android, PC web) sharing logic via `packages/app-core`

## Requirements

- Python 3.11+
- Woolworths NZ account (for live search/cart)
- Node.js 18+ (Expo web + legacy Vite UI)
- Optional: `OPENAI_API_KEY` for LLM meal plans (falls back to template plans without it)

## Setup

```bash
cd woolworths-meal-agent
pip install -e ".[dev]"

# Log in to Woolworths NZ (one-time, ~25s browser login)
woolies login
```

## Usage

```bash
# Interactive CLI
meal-agent

# Expo app (recommended — PC web + phone via Expo Go)
pip install -e ".[dev]"
.\dev-mobile.ps1
# Press w = PC browser  |  Scan QR = Expo Go on phone

# Legacy Vite web UI (during migration)
meal-agent-api
cd apps/web && npm install && npm run dev   # http://localhost:5173

# Non-interactive demo with sample profile
meal-agent demo

# Export-only (skip cart, produce shopping list)
meal-agent run --export-only
```

## Mobile & cross-platform development

The Expo app lives in `apps/mobile/`. Shared TypeScript types and API client are in `packages/app-core/`.

### PC browser (Expo web)

```powershell
meal-agent-api
cd apps/mobile
$env:EXPO_PUBLIC_API_URL="http://127.0.0.1:8000"
npx expo start --web
```

Or run `.\dev-mobile.ps1` from the repo root and press **w**.

### Phone (Expo Go)

The mobile app targets **Expo SDK 54**, compatible with the standard Expo Go app from the App Store / Play Store.

**OpenAI:** The phone does not need its own API key. It calls your PC's `meal-agent-api`, which reads `OPENAI_API_KEY` from the project `.env` file — the same setup as the desktop web app. Restart the API after changing `.env`.

1. Start the API bound to all interfaces (default): `meal-agent-api` listens on `0.0.0.0:8000`.
2. Find your PC's LAN IP (e.g. `192.168.1.42`).
3. Set the API URL and start Expo:

```powershell
$env:EXPO_PUBLIC_API_URL="http://192.168.1.42:8000"
cd apps/mobile
npx expo start
```

4. Scan the QR code with Expo Go (same Wi‑Fi as your PC).

### Woolworths connect by platform

| Platform | Connect flow |
|----------|--------------|
| Local PC / Expo web | API opens your default browser; cookies imported server-side |
| Hosted / Expo web | No Woolworths connect — cart is Coming soon (Woolworths / FreshChoice / New World) |
| iOS / Android | In-app WebView sign-in → cookies sent to `POST /api/session/woolworths/import-cookies` |
| View trolley (mobile) | System in-app browser via `expo-web-browser` |

## Web UI

Six-step wizard: **Preferences → Choose Chef → Meal Plan → Recipes → Shop List → Cart**

- FastAPI backend in `apps/api/` wraps the same orchestrator as the CLI
- **Expo + React Native** frontend in `apps/mobile/` (primary)
- Legacy React + Tailwind frontend in `apps/web/` (Vite, deprecated)
- Web: no Woolworths connect — cart shows **Fill shopping cart, coming soon**
- Phone: in-app WebView Connect still available
- Optional account sign-in for hosted multi-user deployments (Phase 2)

## Project structure

```
packages/
  shared/          # Pydantic models (UserProfile, MealPlan, GroceryLineItem)
  meal_planner/    # LLM + template meal planning
  woolworths/      # Product search, resolver, export
  agent/           # Orchestration, budget engine, review gate
  app-core/        # Shared TS types + session-aware API client
apps/
  cli/             # Rich terminal UI
  api/             # FastAPI web backend
  mobile/          # Expo Router app (iOS, Android, web)
  browser-extension/ # Hosted Woolworths one-click connect (Chrome/Edge/Firefox/Safari Mac)
  web/             # Legacy Vite React UI
tests/             # Unit + integration smoke tests
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Enables LLM meal planning (optional) |
| `OPENAI_MODEL` | Model id (default: `gpt-4o-mini`) |
| `MEAL_AGENT_RELOAD` | Set to `1` to auto-reload API on code changes (off by default on Windows — reload hangs there) |
| `EXPO_PUBLIC_API_URL` | API base URL for Expo app (e.g. `http://192.168.1.x:8000` on LAN) |
| `MEAL_AGENT_ACCESS_CODE` | When set, API requires `X-Access-Code` (hosted testers use `usertest1`) |
| `MEAL_AGENT_CORS_ORIGINS` | Extra allowed CORS origins (comma-separated), e.g. GitHub Pages URL |
| `MEAL_AGENT_COOKIE_SECURE` | Set `1` on HTTPS hosts so session cookies use `Secure` + `SameSite=None` |
| `NDA_SHEETS_WEBHOOK_URL` | Google Apps Script web app URL — appends NDA acceptances to your Sheet |
| `NDA_SHEETS_SECRET` | Shared secret (must match Script property `NDA_SECRET`) |

## Hosted tester deploy (GitHub Pages + Render free)

Share a public webpage + access code **`usertest1`**. The free Render API may sleep after ~15 minutes idle (first request can take 30–60s).

### 1. API on Render

1. Push this repo to GitHub.
2. In [Render](https://render.com), create a **Web Service** from the repo (or use `render.yaml` Blueprint).
3. Set env vars:
   - `OPENAI_API_KEY` — your key
   - `MEAL_AGENT_ACCESS_CODE=usertest1`
   - `MEAL_AGENT_CORS_ORIGINS=https://<you>.github.io` (or `https://<you>.github.io/<repo>` for project Pages)
   - `MEAL_AGENT_COOKIE_SECURE=1`
   - `NDA_SHEETS_WEBHOOK_URL` — Google Apps Script web app URL (see below)
   - `NDA_SHEETS_SECRET` — long random string (same as Script property `NDA_SECRET`)
4. Optional: attach a disk at `/app/data` (Woolworths sessions / local NDA mirror). NDA proof for you is the Google Sheet — disk is not required for that.
5. Note the service URL, e.g. `https://meal-agent-api.onrender.com`.

### 1b. NDA → Google Sheet (free)

Signed NDAs append a row to a spreadsheet you own. Setup:

1. Create a Google Sheet with three tabs in mind: **Summary** (read first), **Feedback**, **Acceptances**.
2. **Extensions → Apps Script** — paste [`docs/nda-google-sheets-apps-script.js`](docs/nda-google-sheets-apps-script.js), save.
3. **Project Settings → Script properties** — add `NDA_SECRET` = your secret.
4. **Deploy → New deployment → Web app** — Execute as: Me; Who has access: Anyone. Copy the URL.
5. Set Render `NDA_SHEETS_WEBHOOK_URL` + `NDA_SHEETS_SECRET` (same secret). Redeploy the API.
6. After pasting an updated script: Deploy → Manage deployments → **New version**. Then in Apps Script run **`resetSheetLayout_`** once to fix headers + rebuild Summary (keeps existing data).
7. **Summary** = investor tallies; **Feedback** = one survey row each; **Acceptances** = who signed the NDA.

### 2. Frontend on GitHub Pages

GitHub Pages requires a **public** repo on the free plan (the access code still gates the app).

1. Repo **Settings → Pages → Source: GitHub Actions**.
2. Add Actions **secret** `EXPO_PUBLIC_API_URL` = your Render API URL (no trailing slash).
3. For this project site, set Actions **variable** `EXPO_PUBLIC_BASE_URL` = `/woolworths-meal-agent`.
4. Push to `main` (workflow: `.github/workflows/deploy-pages.yml`).
5. Site URL: `https://johnnybravo55.github.io/woolworths-meal-agent/`

### 3. Tester instructions

1. Open the GitHub Pages URL.
2. Enter access code **`usertest1`**.
3. Read the NDA, type your full legal name, tick **I Agree**, then **Accept & Begin Beta Test** (once per browser; name + time are appended to the owner’s Google Sheet).
4. Complete preferences → chef → plan → recipes → shop list.
5. Open the cart step to see **Fill shopping cart, coming soon** (Woolworths / FreshChoice / New World). Hosted builds do not connect a Woolworths login or add to trolley yet.
6. Local developers still test real Connect → Add to trolley against `meal-agent-api` on their PC.
7. On the cart "coming soon" page, tap **Feedback** (or wait 10 seconds) and submit the short questionnaire — answers land on the owner's Sheet `Feedback` tab.

**Secrets stay on Render / GitHub Actions** — never commit `.env`.

## Disclaimer

Not affiliated with Woolworths Limited or Woolworths NZ Limited. Uses unofficial community tooling. Use at your own risk.
