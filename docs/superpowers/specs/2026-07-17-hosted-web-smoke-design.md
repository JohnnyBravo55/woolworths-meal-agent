# Hosted web smoke design

**Date:** 2026-07-17  
**Status:** Approved for implementation

## Goal

Prove the hosted Expo web app at GitHub Pages can complete Preferences → Chef → Meal plan → Recipes → Shop list without Woolworths login or cart.

## Decisions

| Topic | Choice |
|-------|--------|
| Approach | Playwright browser automation against the live Pages URL |
| Language | Python (`playwright`) to match `scripts/meal_eval_run.py` |
| Scope | Through shop list only |
| Success | Shop summary visible (`Will add:` / `shop-summary` test id) |
| Hard fail | Navigation to `/connect-woolworths`, cart, or Woolworths sign-in UI |
| Prefs | Scripted fabricated values from `profiles/web_smoke_prefs.json` |
| Access code | `MEAL_AGENT_ACCESS_CODE` env (default `usertest1`) |
| CI | Not required for v1 (Render cold starts are flaky) |

## Flow

1. Open Pages URL (long timeout for API wake-up)
2. Enter access code → Continue
3. Fill fabricated preferences → Continue to chef
4. Select basic chef → Generate meal plan
5. Approve plan → Build shop list
6. Assert shop summary; **stop** (do not approve shop / open cart / connect)

## Harness

- Script: `scripts/web_smoke_run.py`
- Prefer `data-testid` selectors; fall back to button text for current Pages builds
- On failure: screenshot under `output/web-smoke/failure.png`
- Exit `0` pass / `1` fail

## Non-goals

- Cart / Woolworths login
- meal-eval budget/product audit
- Required CI job
- Vite `apps/web` (Pages serves Expo `apps/mobile`)
