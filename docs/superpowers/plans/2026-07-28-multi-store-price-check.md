# Multi-store price check — implementation plan

> **For agentic workers:** Implement task-by-task. Do **not** push until the user has tried locally.

**Goal:** Optional login-free multi-store price check + smart split on shop list (web + mobile).

**Architecture:** `price_check` package with store adapters; API directory + check endpoints; shop-list UI panels.

**Tech stack:** Python/FastAPI, httpx, existing shop list models, React web + Expo mobile via app-core.

## Global constraints

- No store login for price check
- Estimate fallback + note when unmatched
- Do not push to remote until user says so

## Tasks

1. Package models + engine + tests (pure logic)
2. Foodstuffs + Woolworths + FreshChoice adapters + store directory
3. API routes + session selected stores
4. app-core types/client
5. Web + mobile shop list UI
6. Local commit (no push)
