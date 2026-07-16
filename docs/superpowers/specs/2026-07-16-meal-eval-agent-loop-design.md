# Meal-eval agent loop (in-chat)

## Goal

Run N customer journeys against the local API (preferences → chef → meal plan → shopping list → **Woolworths trolley**), cross-check each run, apply **code fixes** when mismatches are found, then continue to the next run. Invoked from Cursor chat with `run meal-eval N` (cart by default; `--shop-only` to skip trolley).

## Cart-phase checks

| Check | Pass criteria |
|-------|----------------|
| **(a) Within budget** | Resolved shop `total` ≤ profile `budget_nzd` |
| **(b) Trolley add** | All addable SKUs added (`failure_count == 0`, no session lost). Offline/blocked lines are failures |
| **(c) Products correct** | Plan↔shop coverage, wrong-product heuristics, allergy/mandatory |

Cart add uses `allow_over_budget=true` so trolley addability is still tested when over budget; budget is scored separately.

Each cart run calls `POST /api/cart/clear` **before** and **after** trolley add so the Woolworths trolley does not accumulate across iterations.

## Decision

**Approach A — chat orchestration + thin API harness.**

- A Python script drives the same HTTP/SSE endpoints the app uses.
- The chat agent (or a Task subagent) performs judgmental cross-check review and applies repo code fixes between runs.
- No Cursor SDK, Automations, or UI browser automation.

## Trigger

```
run meal-eval N
run meal-eval N --chef premium_kenji
```

Default chef selection is round-robin across all six chefs. Optional `--chef` pins one chef for every iteration.

## Prerequisites

- `meal-agent-api` listening on `http://127.0.0.1:8000`
- `OPENAI_API_KEY` set (required for premium chefs; also preferred for Sam)
- `MEAL_AGENT_DEV_PREMIUM=1` in the API environment so premium chefs are selectable without a subscription

## Customer harness

Script: [`scripts/meal_eval_run.py`](../../../scripts/meal_eval_run.py)  
Baseline profile: [`profiles/meal_eval_baseline.json`](../../../profiles/meal_eval_baseline.json)

Per run:

1. `POST /api/session/start`
2. `POST /api/profile` with baseline answers + selected `chef_id`
3. `POST /api/plan/generate` (SSE until `complete` or `error`)
4. `POST /api/plan/approve`
5. `POST /api/shop/resolve` (SSE until `complete` or `error`)
6. Write artifacts under `output/meal-eval/run-{i:03d}-{chef_id}/`

Artifacts:

| File | Contents |
|------|----------|
| `profile.json` | Discovery answers + returned profile |
| `meal_plan.json` | Generated meal plan |
| `resolved_list.json` | Resolved grocery list |
| `session_meta.json` | session id, chef, timings, warnings |
| `audit_findings.json` | Structured findings |
| `audit_report.md` | Human-readable audit summary |

Chef rotation order:

`basic_sam` → `premium_elena` → `premium_kenji` → `premium_moana` → `premium_alex` → `premium_amara`

## Cross-check

Programmatic (in harness):

- `audit_shop_coverage` on plan meals vs ingredients reconstructed from resolved shop lines
- Server `coverage_issues` / `unresolved_ingredients`
- Heuristic wrong-product / missing / orphan-meal checks (aligned with `output/_audit_run.py`)
- Allergy keyword scan when profile lists allergies
- Mandatory-item presence on the shop list

Agent review (in chat):

- Read `audit_report.md` + artifacts
- Classify root cause (planner, shop flatten/repair, resolver, API)
- Apply code fixes; add a focused pytest when reproducible without a full LLM run
- Restart API if server packages changed
- Continue to run `i+1`

## Fix phase rules

- Soft audit failures → fix code → next run
- Hard stop: API down, harness crash, premium blocked without `MEAL_AGENT_DEV_PREMIUM`, OpenAI missing for premium generation

## Out of scope

- Expo / Vite UI clicking
- Cart add / Woolworths login
- Automatic git commits

## Chat rule

[`.cursor/rules/meal-eval.mdc`](../../../.cursor/rules/meal-eval.mdc) — when the user says `run meal-eval N`, follow the loop without re-asking for confirmation.
