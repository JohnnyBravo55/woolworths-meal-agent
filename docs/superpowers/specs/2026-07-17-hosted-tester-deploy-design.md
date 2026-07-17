# Hosted tester deploy design

**Date:** 2026-07-17  
**Status:** Approved for implementation

## Goal

Ship a shareable webpage for early testers to run the full product flow (preferences → meal plan → shop list → own Woolworths trolley) without managing servers ourselves day-to-day.

## Decisions

| Topic | Choice |
|-------|--------|
| Tester scope | Preferences → plan → shop list; supermarket cart fill is coming soon on hosted (local keeps full trolley) |
| Hosting cost | Free tier: static frontend + Render free API (may sleep / cold-start) |
| Woolworths accounts | Each tester connects their own account |
| Access control | Shared code `usertest1` (UI + API), not link-obscurity alone |
| Repo | GitHub as source of truth and Pages deploy source (public on free plan so Pages works; access code still gates the app) |
| Frontend | Expo web static export (`apps/mobile`) on GitHub Pages |
| Backend | FastAPI (`meal-agent-api`) on Render free + persistent disk for `data/` |
| Hosted Woolworths connect | Deferred — cart step shows Coming soon (Woolworths / FreshChoice / New World). Local PC still uses browser cookie import |

## Architecture

- **GitHub Pages** serves the Expo web static build.
- **Render** runs the Python API; env holds `OPENAI_API_KEY`, `MEAL_AGENT_ACCESS_CODE`, `MEAL_AGENT_CORS_ORIGINS`.
- Frontend calls API via bake-in `EXPO_PUBLIC_API_URL` and sends `X-Session-Id` + `X-Access-Code`.
- Hosted cart step is a Coming soon teaser (no cookie bridge / trolley add). Local builds keep Connect → Add to trolley.
- In-memory wizard sessions may reset on Render sleep/redeploy (accepted for v1).

## Access code

- Value: `usertest1` (configured as `MEAL_AGENT_ACCESS_CODE` on Render).
- Web unlock screen stores unlock in `sessionStorage`.
- When the env var is set, API requires `X-Access-Code` on `/api/*` (health left open for probes).
- Local dev: unset env → no gate.

## Non-goals (v1)

- Always-on paid API
- Serverless function rewrite / Redis session store
- App Store / Play Store
- Per-user accounts / Cloudflare Access

## Acceptance

A tester on another network completes preferences → plan → shop and sees **Fill shopping cart, coming soon** using the public link + `usertest1`, with at most a cold-start delay after idle. API rejects requests without the code. Local / meal-eval `--cart` still validates real trolley.
