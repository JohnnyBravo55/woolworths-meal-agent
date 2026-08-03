# Pantry opt-in (recipes) + product rename design

**Date:** 2026-08-03  
**Status:** Approved for implementation planning  
**Surfaces:** Web + mobile (v1 together); CLI / meal-eval use defaults below

## Decision

Stop collecting pantry items on Discovery. The planner tags staple ingredients as pantry. On the recipes step, show a **Required pantry items** checklist; users tick only what they need to buy **before** product search. Unticked pantry items are assumed at home and never resolved into the shop list.

Also rename the user-facing product from **Woolworths Meal Agent** to **Meal Agent** (Woolworths remains the store integration, not the product name).

## Approach

**Tag on ingredients + session buy set (Approach A)**

- Each `Ingredient` carries `is_pantry: bool`.
- Session holds `pantry_to_buy: list[str]` (normalized names the user ticked).
- Shop flatten/resolve skips pantry ingredients unless their name matches `pantry_to_buy`.

Rejected: separate plan-level pantry list only (B); post-hoc classify after generation (C).

## Data model

### Ingredient

Add:

```text
is_pantry: bool = False
```

Planner prompt instructs the LLM to set `is_pantry: true` only for staples such as sauces, spices, salt, pepper, sugar, stock, dried herbs/powders (e.g. soy sauce, sweet chilli, fish sauce, cumin, paprika, garlic powder). Fresh produce, proteins, dairy, bread, and meal-specific bulk items stay `false`.

Default `false` if omitted → item stays on the normal shop list (safe over-buy).

### Session / conversation state

Add:

```text
pantry_to_buy: list[str] = []
```

- Empty (default) = assume household has all pantry items → never buy them.
- CLI and meal-eval leave this empty.
- Reset to `[]` and clear any resolved shop list when the meal plan is regenerated or the chef changes.

### Profile

- Remove Discovery UI write path for pantry (web + mobile).
- `UserProfile.pantry_items` may remain for compatibility but is always treated as empty for shop exclusion; do not use it to strip ingredients.
- Replace `exclude_pantry_ingredients(profile.pantry_items)` with the `is_pantry` + `pantry_to_buy` gate.
- `assume_pantry_staples` is unused for this flow; remove from prompts or leave inert — not user-facing.

### API

Before resolve, clients set ticks via a small update (dedicated endpoint or existing session patch), e.g.:

```text
POST /api/pantry/to-buy  { "items": ["soy sauce", "salt"] }
```

Resolve must read the current `pantry_to_buy`. If the update fails, block resolve with a clear error; do not search with stale ticks.

## Shop pipeline

1. Collect plan ingredients as today (mandatory merge, allergy filters, dedupe).
2. For each ingredient with `is_pantry == true`: include in the resolve set **only if** it matches an entry in `pantry_to_buy` (same fuzzy normalize/`is_in_pantry`-style matching used today so close variants share a tick).
3. Non-pantry ingredients always eligible to shop.
4. Mandatory items always shop even if a name overlaps a pantry staple.
5. Ticked pantry items resolve like any other line (SKU, budget, cart, unresolved warnings).

## UX

### Discovery

Remove “Already have at home (pantry)” (web + mobile) and any review badge that echoed that field.

### Recipes (web + mobile)

Above the week of recipes:

| Element | Copy / behavior |
|---|---|
| Title | **Required pantry items** |
| Helper above checkboxes | **Tick to add item to shopping list** |
| Controls | Deduped checklist of pantry-tagged names from the plan |
| Default | Unchecked = have at home |
| Checked | Add name to `pantry_to_buy` |
| Empty plan pantry | Hide the whole box |

Ordering: first-seen across meals (recipe flow order), not alphabetical.

Ticks only update session state until the user runs product search (“Search Woolworths” / “Build shop list”). That action persists `pantry_to_buy` then resolves.

If a cached shop list exists and ticks change, invalidate the cache and require a fresh search.

### Per-recipe note

Do not list full pantry line items in the recipe ingredient list. Show a light note when the meal has pantry-tagged ingredients:

```text
Uses pantry: soy sauce, salt, pepper
```

Omit the note when the meal has none.

### Download recipes (v1)

Same per-meal pantry note. A top-of-export pantry checklist is optional, not required.

## Product rename: Meal Agent

User-facing product name becomes **Meal Agent** (not “Woolworths Meal Agent”).

**In scope**

- Web header title
- Mobile app display name / wizard / access-gate titles (`app.json` `name`, WizardShell, AccessCodeGate)
- CLI Rich title
- FastAPI `title` and similar user-visible API labels
- Docstrings/handoff lines that name the product as “Woolworths Meal Agent”

**Out of scope**

- Repo / package / folder names (`woolworths-meal-agent`, `woolworths_adapter`, etc.)
- Store-specific copy (“Connect Woolworths”, trolley, Woolworths search)
- Browser extension name already framed as “Meal Agent — Woolworths Connect” (keep; Woolworths is the connect target)

## Edge cases

| Case | Behavior |
|---|---|
| No pantry tags | Hide box; shop unchanged |
| LLM omits `is_pantry` | Default `false` → normal shop item |
| LLM over-tags | User can tick to buy; tighten planner examples; no keyword backstop in v1 |
| Name variants | Fuzzy match ticks to ingredients |
| Re-plan / new chef | Reset `pantry_to_buy`; clear resolved list |
| Automation | Empty `pantry_to_buy`; audits must not fail for missing pantry SKUs |

## Testing

Focused unit tests (no full LLM/cart run):

- Flatten: pantry + empty `pantry_to_buy` → excluded; pantry + matching tick → included
- Deduped pantry list helper from a sample plan
- Recipe note helper: pantry names only; omitted when empty
- Schema parse: ingredient with/without `is_pantry`
- Discovery no longer requires pantry answers; empty `pantry_items` still works

## Non-goals

- Keyword/heuristic pantry classifier in v1
- Persisting pantry inventory across sessions/users
- Auto-buying pantry on CLI/meal-eval
- Renaming the git repo or Woolworths integration packages
