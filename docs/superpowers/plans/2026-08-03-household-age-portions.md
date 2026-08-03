# Household Age Portions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users set adult + child age-band household composition so meals are portioned with ceil-to-0.5 adult-equivalent servings and kid-friendly chef guidance when children ≤12 are present.

**Architecture:** Add pure portion helpers in `shared`, extend `UserProfile` / discovery answers with adults + children age bands (keep `household_size` derived), thread `adult_equivalent_servings` into planner prompts, cart caps, and budget scale, and replace the People stepper in web/mobile discovery with the approved inline ages UI.

**Tech Stack:** Python/Pydantic, pytest, TypeScript (app-core), React web + Expo mobile.

## Global Constraints

- Adult portions = people 13+; child portions = 12 and under
- Age bands: `1-3`→0.35, `4-6`→0.50, `7-9`→0.65, `10-12`→0.80
- Servings for chef/caps = exact adult-equivalent **ceil to next 0.5**
- UI: no factor labels / must-total copy; ages expand when children > 0; band sum must match child total on Continue
- Kid-friendly hard bias when any child ≤12 unless likes/other_instructions override
- Legacy profiles: missing fields → treat `household_size` as all adults
- UI total headcount cap 8; keep writing `household_size` for compatibility

---

## File map

| File | Responsibility |
|------|----------------|
| `packages/shared/src/shared/portions.py` | Age-band constants, exact AE, ceil-to-half, band-sum check, servings from profile fields |
| `packages/shared/src/shared/models.py` | `ChildrenAgeBands`, profile fields, model_validator migration |
| `packages/shared/src/shared/__init__.py` | Export helpers/models as needed |
| `tests/test_portions.py` | Portion math + validation tests |
| `tests/test_models.py` | Legacy profile load |
| `apps/api/.../schemas.py` | DiscoveryAnswers fields |
| `packages/agent/.../conversation.py` | answers → profile |
| `packages/app-core/src/types.ts` | TS types/defaults/profileToAnswers |
| `apps/web/.../DiscoveryStep.tsx` | Household UI |
| `apps/mobile/app/discovery.tsx` | Household UI |
| `packages/meal_planner/.../planner.py` | Constraints + kid-friendly note + template scale |
| `packages/meal_planner/.../chefs.py` | Portion wording for AE servings |
| `packages/meal_planner/.../budget_feasibility.py` | Scale by AE servings |
| `packages/woolworths/.../quantities.py` | Caps use float servings |
| `packages/woolworths/.../resolver.py` | Pass servings |
| `packages/price_check/.../pricing.py` | `needed_kg` people = servings |
| `profiles/meal_eval_baseline.json` | Optional adults fields |

---

### Task 1: Portion math helpers

**Files:**
- Create: `packages/shared/src/shared/portions.py`
- Create: `tests/test_portions.py`
- Modify: `packages/shared/src/shared/__init__.py` (export if useful)

**Interfaces:**
- Produces:
  - `AGE_BAND_FACTORS: dict[str, float]` keys `"1-3"|"4-6"|"7-9"|"10-12"`
  - `ceil_to_half(value: float) -> float`
  - `adult_equivalent_exact(adults: int, bands: Mapping[str, int]) -> float`
  - `adult_equivalent_servings(adults: int, bands: Mapping[str, int]) -> float`
  - `age_bands_sum(bands: Mapping[str, int]) -> int`
  - `age_bands_match_children(bands: Mapping[str, int], children_under_13: int) -> bool`

- [ ] **Step 1: Write failing tests** in `tests/test_portions.py`

```python
from shared.portions import (
    adult_equivalent_exact,
    adult_equivalent_servings,
    age_bands_match_children,
    ceil_to_half,
)

def test_ceil_to_half():
    assert ceil_to_half(3.15) == 3.5
    assert ceil_to_half(3.0) == 3.0
    assert ceil_to_half(2.01) == 2.5
    assert ceil_to_half(0) == 0.0

def test_adult_equivalent_example():
    bands = {"1-3": 0, "4-6": 1, "7-9": 1, "10-12": 0}
    assert abs(adult_equivalent_exact(2, bands) - 3.15) < 1e-9
    assert adult_equivalent_servings(2, bands) == 3.5

def test_age_bands_match():
    bands = {"1-3": 0, "4-6": 1, "7-9": 1, "10-12": 0}
    assert age_bands_match_children(bands, 2)
    assert not age_bands_match_children(bands, 1)
```

- [ ] **Step 2: Run** `pytest tests/test_portions.py -v` — expect FAIL (import error)
- [ ] **Step 3: Implement** `portions.py` with math.ceil(value * 2) / 2.0 for positive values; 0 stays 0
- [ ] **Step 4: Run** tests — PASS
- [ ] **Step 5: Commit** `feat: add adult-equivalent portion helpers`

---

### Task 2: UserProfile schema + legacy migration

**Files:**
- Modify: `packages/shared/src/shared/models.py`
- Modify: `tests/test_models.py`

**Interfaces:**
- Produces on `UserProfile`:
  - `adults: int = 2` (ge=0 or ge=1; use ge=0, ensure household_size ≥ 1 via validator)
  - `children_under_13: int = 0` (ge=0)
  - `children_age_bands: ChildrenAgeBands` with ints default 0
  - `adult_equivalent_servings: float` computed property or field set in validator
- Keep `household_size` required for back-compat but sync in `model_validator(mode="before")`:
  - If adults/children missing and household_size present → adults=household_size, children=0
  - Always set household_size = adults + children_under_13 after parse
  - Compute/store `adult_equivalent_servings` via portions helper (use empty bands when children=0)

```python
class ChildrenAgeBands(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    band_1_3: int = Field(default=0, ge=0, alias="1-3")
    band_4_6: int = Field(default=0, ge=0, alias="4-6")
    band_7_9: int = Field(default=0, ge=0, alias="7-9")
    band_10_12: int = Field(default=0, ge=0, alias="10-12")

    def as_factor_map(self) -> dict[str, int]:
        return {"1-3": self.band_1_3, "4-6": self.band_4_6, "7-9": self.band_7_9, "10-12": self.band_10_12}
```

Prefer serialization with aliases `"1-3"` etc. so JSON matches the spec.

- [ ] **Step 1: Test** legacy `UserProfile(household_size=3, meals_requested=..., budget_nzd=100)` → adults=3, children=0, servings=3.0
- [ ] **Step 2: Test** adults=2 + bands 4-6=1,7-9=1 → household_size=4, servings=3.5
- [ ] **Step 3: Implement model changes**
- [ ] **Step 4: pytest tests/test_models.py tests/test_portions.py** — PASS
- [ ] **Step 5: Commit** `feat: add household age fields to UserProfile`

---

### Task 3: API DiscoveryAnswers + conversation mapping

**Files:**
- Modify: `apps/api/src/meal_agent_api/schemas.py`
- Modify: `packages/agent/src/agent/conversation.py`
- Modify: `tests/test_budget_from_answers.py` (and add band validation test if none)

**Interfaces:**
- `DiscoveryAnswers` adds:
  - `adults: int = 2`
  - `children_under_13: int = 0`
  - `children_age_bands: dict[str, int] = {"1-3":0,"4-6":0,"7-9":0,"10-12":0}`
  - Keep `household_size` derived in `to_answers_dict` / conversation as adults+children
- `create_profile_from_answers`: read new fields; if only household_size present, legacy path; validate band sum when children>0 (raise ValueError with message suitable for API 400)

- [ ] Implement + tests for answers→profile
- [ ] Commit `feat: map discovery adults/children into profile`

---

### Task 4: app-core TypeScript types

**Files:**
- Modify: `packages/app-core/src/types.ts`
- Modify: `packages/app-core/src/wizard-nav.ts` if fingerprint should include new fields (include adults/children/bands in fingerprint JSON)

- [ ] Extend `DiscoveryAnswers`, `DEFAULT_ANSWERS`, `profileToAnswers` (derive adults from household_size when missing)
- [ ] Commit `feat: add household age fields to app-core types`

---

### Task 5: Web + mobile discovery UI

**Files:**
- Modify: `apps/web/src/steps/DiscoveryStep.tsx`
- Modify: `apps/mobile/app/discovery.tsx`

**Behaviour:**
- Replace People with Adult portions / Child portions steppers
- Cap: adults+children ≤ 8
- When children>0 show Ages of children four steppers
- On Continue: if children>0 and band sum ≠ children, show “Assign an age for each child” and block
- Sync `household_size = adults + children_under_13` on change for any leftover consumers

- [ ] Implement both UIs
- [ ] Commit `feat: household age-band steppers in discovery UI`

---

### Task 6: Planner constraints + chef kid-friendly + templates

**Files:**
- Modify: `packages/meal_planner/src/meal_planner/planner.py`
- Modify: `packages/meal_planner/src/meal_planner/chefs.py`
- Modify: `tests/test_meal_planner.py` (assert constraint keys when kids present)

**Behaviour:**
- Constraints include adults, children_under_13, children_age_bands, adult_equivalent_servings, household_size
- Portion note: size ingredients for adult_equivalent_servings (fractional OK)
- When children_under_13>0: add kid_friendly_rules hard bias text + honour likes/other_instructions override
- Update `_NZ_BASE` portion sentence to mention adult-equivalent servings
- Offline templates: scale qty by `adult_equivalent_servings / 2.0` when building from templates

- [ ] Implement + test constraint payload
- [ ] Commit `feat: child-aware planner portions and kid-friendly chef rules`

---

### Task 7: Cart caps, price needed_kg, budget scale

**Files:**
- Modify: `packages/woolworths/src/woolworths_adapter/quantities.py` — accept `household_size: float = 2` (servings)
- Modify: `packages/woolworths/src/woolworths_adapter/resolver.py` — pass `profile.adult_equivalent_servings`
- Modify: `packages/price_check/src/price_check/pricing.py` — people = servings float
- Modify: `packages/meal_planner/src/meal_planner/budget_feasibility.py` — `scale = max(1.0, servings / 2.0)`
- Modify: existing quantity/pricing tests if assertions assume int headcount only

- [ ] Implement + run relevant pytest
- [ ] Commit `feat: scale cart and budget caps by adult-equivalent servings`

---

### Task 8: Smoke + finalize

- [ ] Run `pytest tests/test_portions.py tests/test_models.py tests/test_meal_planner.py tests/test_price_check_pricing.py tests/test_budget.py -q`
- [ ] Fix regressions from UserProfile new required-ish fields (defaults should make most tests pass)
- [ ] Commit any fixes; push

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Adults + children fields | 2, 3, 4 |
| Age bands + factors | 1, 2 |
| Ceil to 0.5 | 1 |
| Inline UI expand | 5 |
| Band sum validation | 3, 5 |
| Planner + kid-friendly | 6 |
| Cart/budget scale | 7 |
| Legacy migration | 2 |
| Template scale | 6 |
