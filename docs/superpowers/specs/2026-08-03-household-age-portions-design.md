# Household age bands and child-aware portioning

**Date:** 2026-08-03  
**Status:** Approved for implementation

## Goals

1. Let users set **adult portions (13+)** and **child portions (12 and under)** in discovery preferences.
2. When there are children, collect counts per age band so meals can be portioned with adult-equivalent factors.
3. Size planner ingredients, cart quantity caps, and budget scaling from **fractional adult-equivalent servings**, ceiled to the next 0.5.
4. When any child ≤12 is present, chefs plan **mild, family-friendly** meals (hard bias), unless the user asks otherwise in likes / other instructions.

## Decisions

| Topic | Choice |
|-------|--------|
| Replace People stepper | Yes — adults + children under 13 |
| Adult definition | People 13+ (no separate teens field) |
| Child definition | Children 12 and under |
| Age entry UI | Inline expand when children > 0 (left-style stacked steppers) |
| Age bands | 1–3, 4–6, 7–9, 10–12 |
| Band sum | Must equal child total before Continue; no “must total” / factor labels in UI |
| Portion factors | 1–3 → 0.35; 4–6 → 0.50; 7–9 → 0.65; 10–12 → 0.80; adult → 1.0 |
| Serving number for chef/caps | Exact adult-equivalent, then **ceil to next 0.5** |
| Kid-friendly chef | Hard bias when any ≤12 child; override via likes / other instructions |
| Legacy profiles | Missing new fields → treat `household_size` as all adults |
| Platforms | Web + mobile discovery; API profile/planner/quantity paths |

## Data model

Add to `DiscoveryAnswers` / `UserProfile` (names may match existing style):

| Field | Type | Notes |
|-------|------|--------|
| `adults` | int ≥ 1 | Default 2 |
| `children_under_13` | int ≥ 0 | Default 0 |
| `children_age_bands` | object | `{ "1-3", "4-6", "7-9", "10-12" }` counts; required when children > 0 |

Derived / kept for compatibility:

- `household_size` = `adults + children_under_13` (persist; keep writing for existing consumers)
- `adult_equivalent_exact` = adults×1.0 + Σ(band_count × factor)
- `adult_equivalent_servings` = ceil_to_half(`adult_equivalent_exact`)

Example: 2 adults + one 4–6 + one 7–9 → exact 3.15 → servings **3.5**.

### Migration

- Old JSON with only `household_size`: `adults = household_size`, `children_under_13 = 0`, empty bands, servings = household_size.
- New profiles always recompute `household_size` from adults + children.

## UI

**Household card (web + mobile):**

1. Stepper: **Adult portions** (subtitle: People 13+)
2. Stepper: **Child portions** (subtitle: Children 12 and under)
3. If children > 0, expand **Ages of children** with four steppers: 1–3 / 4–6 / 7–9 / 10–12 years
4. No on-screen portion factors, adult-equivalent preview, or “must total N” copy
5. If Continue while band sum ≠ child total → short validation error only (e.g. “Assign an age for each child”)
6. UI headcount cap remains 8 total people

Ages hide again if children returns to 0 (clear or ignore band counts).

## Portioning behaviour

Use adult-equivalent servings (after ceil-to-0.5) in:

1. **Meal planner constraints / chef prompts** — size ingredients for that serving total; include breakdown (adults + band counts) so the model understands mixed ages.
2. **Cart quantity caps** (`normalize_cart_quantity` / related helpers) — scale people-based caps by servings, not raw headcount.
3. **Budget feasibility** — scale estimates by servings (same basis as above).

Leftover dinner bump (~1.5× protein/carb) continues to apply on top of already-portioned meal ingredients; do not multiply leftover scale by headcount.

Offline/template meals: scale ingredient amounts by `adult_equivalent_servings / baseline_servings` (baseline = current template assumption, typically 2) so kid households are not fully adult-sized.

## Chef kid-friendly rules

When `children_under_13 > 0`:

- Avoid spicy heat, very adventurous / “out there” dishes, and strongly fermented or intense flavours as the default for the **whole** plan.
- Prefer mild, familiar, family-friendly meals that still fit the selected chef’s cuisine identity at a gentler level (e.g. Kenji without heavy chilli).
- If `likes` or `other_instructions` explicitly request spice, adventurous food, or similar, honour the user override.

When no children under 13: no extra kid-friendly constraints.

## API / code touchpoints

- `packages/shared/.../models.py` — `UserProfile`
- `apps/api/.../schemas.py` — `DiscoveryAnswers`
- `packages/app-core` types + defaults + `profileToAnswers`
- `packages/agent/.../conversation.py` — answers → profile
- Web `DiscoveryStep.tsx`, mobile `discovery.tsx`
- `packages/meal_planner` planner constraints + chef base/system guidance
- `packages/woolworths` quantity helpers; budget feasibility helpers
- Fixtures: `profiles/meal_eval_baseline.json` and related tests

## Testing

- Unit: exact adult-equivalent + ceil-to-0.5 cases
- Unit: band-sum validation (match / mismatch)
- Unit: legacy profile load → all adults
- Unit/integration: planner constraint payload includes composition + servings when kids present
- UI: ages section visibility toggles with children count (web and/or mobile as practical in existing test setup)

## Out of scope

- Separate mild “kids plate” SKUs or dual menus per meal
- Teen-specific field (13+ counted as adults)
- Per-child named ages (only band counts)
- Changing chef roster / new kid-only chef
- Rounding policy other than ceil-to-0.5 for planner/caps
