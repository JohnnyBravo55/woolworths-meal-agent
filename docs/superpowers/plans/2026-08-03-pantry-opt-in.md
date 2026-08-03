# Pantry Opt-In + Meal Agent Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tag pantry staples on ingredients, let users tick missing ones on the recipes step before search, and rename the product to Meal Agent.

**Architecture:** Add `Ingredient.is_pantry` and session `pantry_to_buy`. Shop flatten/coverage/resolve skip pantry ingredients unless ticked. Recipes UI shows a required-pantry checklist + per-meal “Uses pantry” notes. Discovery pantry field removed. User-facing “Woolworths Meal Agent” → “Meal Agent”.

**Tech Stack:** Python/Pydantic, pytest, TypeScript (app-core), React web, Expo mobile, FastAPI.

## Global Constraints

- Pantry = LLM-tagged staples (sauces/spices/salt/pepper/sugar/stock/powders); default `is_pantry=False` if omitted
- Unticked pantry → assume owned → never shop; CLI/meal-eval leave `pantry_to_buy=[]`
- Tick before search; changing ticks invalidates cached shop list
- Recipes: top box “Required pantry items” + helper “Tick to add item to shopping list”; per-meal `Uses pantry: …`
- Web + mobile together; product rename user-facing only (not repo/package names)
- Mandatory items always shop even if name overlaps pantry
- Reset `pantry_to_buy` on re-plan / chef change

---

## File map

| File | Responsibility |
|------|----------------|
| `packages/shared/src/shared/models.py` | `Ingredient.is_pantry`; `ConversationState.pantry_to_buy` |
| `packages/meal_planner/src/meal_planner/pantry.py` | Gate helpers, collect/dedupe pantry names, meal note |
| `packages/meal_planner/src/meal_planner/ingredients.py` | Flatten uses `is_pantry` + `pantry_to_buy` |
| `packages/meal_planner/src/meal_planner/shop_coverage.py` | Coverage ignores owned pantry |
| `packages/meal_planner/src/meal_planner/planner.py` | Prompt + schema `is_pantry`; parse flag; template staples |
| `packages/woolworths/.../resolver.py` | Skip owned pantry (session list, not profile) |
| `packages/agent/.../orchestrator.py` | Pass `pantry_to_buy`; reset on plan regen |
| `packages/agent/.../conversation.py` | Stop requiring/writing pantry answers (empty ok) |
| `apps/api/.../schemas.py` | StateResponse + pantry body; DiscoveryAnswers keep field optional |
| `apps/api/.../main.py` | `POST /api/pantry/to-buy`; resolve uses session ticks |
| `packages/app-core/src/types.ts` | `is_pantry`, `pantry_to_buy`, Meal ingredient type |
| `packages/app-core/src/api/client.ts` | `setPantryToBuy` |
| `apps/web/.../DiscoveryStep.tsx` | Remove pantry field/badge |
| `apps/web/.../RecipesStep.tsx` | Pantry box + notes |
| `apps/web/src/App.tsx` | Wire ticks → API before resolve; title rename |
| `apps/mobile/app/discovery.tsx` | Remove pantry field |
| `apps/mobile/app/recipes.tsx` | Pantry box + notes |
| `apps/mobile/components/WizardShell.tsx` / `AccessCodeGate.tsx` / `app.json` | Rename |
| `apps/cli/.../main.py` | Title rename |
| `apps/api/.../main.py` | FastAPI title rename |
| `tests/test_pantry_opt_in.py` | Gate / flatten / helpers |

---

### Task 1: Pantry helpers + Ingredient flag + flatten gate

**Files:**
- Modify: `packages/shared/src/shared/models.py`
- Modify: `packages/meal_planner/src/meal_planner/pantry.py`
- Modify: `packages/meal_planner/src/meal_planner/ingredients.py`
- Modify: `packages/meal_planner/src/meal_planner/shop_coverage.py`
- Create: `tests/test_pantry_opt_in.py`

**Interfaces:**
- Produces:
  - `Ingredient.is_pantry: bool = False`
  - `ConversationState.pantry_to_buy: list[str] = []`
  - `is_owned_pantry(ingredient: Ingredient, pantry_to_buy: list[str]) -> bool` — True when `is_pantry` and name does **not** match `pantry_to_buy` (fuzzy via existing `is_in_pantry`)
  - `collect_required_pantry(meals: list) -> list[str]` — first-seen deduped pantry names
  - `pantry_uses_note(meal: Meal) -> str | None` — `"Uses pantry: a, b"` or None
  - `build_shopping_ingredients(meals, profile, pantry_to_buy: list[str] | None = None)`

- [ ] **Step 1: Write failing tests** in `tests/test_pantry_opt_in.py`

```python
from shared.models import Ingredient, Meal, MealSlot, MealsRequested, UserProfile
from meal_planner.pantry import (
    collect_required_pantry,
    is_owned_pantry,
    pantry_uses_note,
)
from meal_planner.ingredients import build_shopping_ingredients


def _profile(**kwargs) -> UserProfile:
    return UserProfile(
        household_size=2,
        days=2,
        meals_requested=MealsRequested(dinner=2, lunch=0, breakfast=0, snacks=0),
        budget_nzd=100,
        **kwargs,
    )


def test_is_owned_pantry_respects_ticks():
    soy = Ingredient(name="soy sauce", quantity=1, unit="bottle", is_pantry=True)
    assert is_owned_pantry(soy, []) is True
    assert is_owned_pantry(soy, ["soy sauce"]) is False
    chicken = Ingredient(name="chicken thighs", quantity=800, unit="g", is_pantry=False)
    assert is_owned_pantry(chicken, []) is False


def test_collect_and_note_first_seen():
    m1 = Meal(
        name="Stir fry",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="",
        ingredients=[
            Ingredient(name="chicken", quantity=400, unit="g"),
            Ingredient(name="soy sauce", quantity=1, unit="tbsp", is_pantry=True),
            Ingredient(name="salt", quantity=1, unit="tsp", is_pantry=True),
        ],
        steps=[],
    )
    m2 = Meal(
        name="Noodles",
        slot=MealSlot.DINNER,
        day_label="Tuesday",
        description="",
        ingredients=[
            Ingredient(name="noodles", quantity=400, unit="g"),
            Ingredient(name="soy sauce", quantity=1, unit="tbsp", is_pantry=True),
        ],
        steps=[],
    )
    assert collect_required_pantry([m1, m2]) == ["soy sauce", "salt"]
    assert pantry_uses_note(m1) == "Uses pantry: soy sauce, salt"
    assert pantry_uses_note(m2) == "Uses pantry: soy sauce"


def test_flatten_excludes_owned_pantry_includes_ticked():
    meal = Meal(
        name="Stir fry",
        slot=MealSlot.DINNER,
        day_label="Monday",
        description="chicken dinner",
        ingredients=[
            Ingredient(name="chicken thighs", quantity=800, unit="g"),
            Ingredient(name="soy sauce", quantity=1, unit="bottle", is_pantry=True),
        ],
        steps=["Cook"],
    )
    names_default = {i.name for i in build_shopping_ingredients([meal], _profile())}
    assert "soy sauce" not in names_default
    assert "chicken thighs" in names_default
    names_buy = {
        i.name for i in build_shopping_ingredients([meal], _profile(), pantry_to_buy=["soy sauce"])
    }
    assert "soy sauce" in names_buy
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
cd C:\Users\marku\Projects\woolworths-meal-agent
python -m pytest tests/test_pantry_opt_in.py -v
```

- [ ] **Step 3: Implement models + pantry helpers**

In `models.py` on `Ingredient` add `is_pantry: bool = False`. On `ConversationState` add `pantry_to_buy: list[str] = Field(default_factory=list)`.

In `pantry.py`:

```python
def is_owned_pantry(ingredient: Ingredient, pantry_to_buy: list[str] | None) -> bool:
    if not ingredient.is_pantry:
        return False
    return not is_in_pantry(ingredient.name, pantry_to_buy or [])


def collect_required_pantry(meals: list) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for meal in meals:
        for ing in getattr(meal, "ingredients", []) or []:
            if not getattr(ing, "is_pantry", False):
                continue
            name = normalize_pantry_item(ing.name)
            if not name or name in seen:
                continue
            seen.add(name)
            ordered.append(name)
    return ordered


def pantry_uses_note(meal) -> str | None:
    names = collect_required_pantry([meal])
    if not names:
        return None
    return "Uses pantry: " + ", ".join(names)
```

(Import `normalize_pantry_item` already in file; use it.)

- [ ] **Step 4: Wire flatten + coverage**

`build_shopping_ingredients(..., pantry_to_buy: list[str] | None = None)`:
- Replace `exclude_pantry_ingredients(items, profile.pantry_items)` with filtering out items where `is_owned_pantry(item, pantry_to_buy)`.
- In `_ensure_meal_ingredients_present`, skip when `is_owned_pantry(ing, pantry_to_buy)` (pass `pantry_to_buy` through).
- Do **not** use `profile.pantry_items` for exclusion anymore.

`shop_coverage._required_shop_ingredients`: skip ingredients where `is_owned_pantry(ing, pantry_to_buy)` — add `pantry_to_buy` param through call chain from `repair_shop_coverage` / `link_meals_to_shop_items` / audit helpers that currently take `profile` only. Prefer: pass `pantry_to_buy` into functions that call `_required_shop_ingredients`; default `None` → treat as `[]`.

Any call site of `build_shopping_ingredients` must still compile: default `pantry_to_buy=None` means owned pantry excluded.

- [ ] **Step 5: Run tests — expect PASS**

```powershell
python -m pytest tests/test_pantry_opt_in.py tests/test_shop_coverage.py tests/test_meal_quality.py tests/test_heal_coverage.py -v
```

Update fixtures that relied on `profile.pantry_items` for exclusion: set `is_pantry=True` on those ingredients in test meals instead (or keep profile field unused and adjust expectations).

- [ ] **Step 6: Commit**

```powershell
git add packages/shared/src/shared/models.py packages/meal_planner/src/meal_planner/pantry.py packages/meal_planner/src/meal_planner/ingredients.py packages/meal_planner/src/meal_planner/shop_coverage.py tests/test_pantry_opt_in.py tests/test_shop_coverage.py tests/test_heal_coverage.py
git commit -m "Gate shop flatten on is_pantry and pantry_to_buy ticks."
```

---

### Task 2: Planner tags `is_pantry`

**Files:**
- Modify: `packages/meal_planner/src/meal_planner/planner.py`
- Modify: `packages/woolworths/src/woolworths_adapter/resolver.py` (skip owned pantry via ingredient flag + passed buy list if available; stop using `profile.pantry_items` alone)
- Modify: `packages/agent/src/agent/orchestrator.py` (pass `state.pantry_to_buy` into `build_shopping_ingredients`; clear `pantry_to_buy` when regenerating plan)

**Interfaces:**
- Consumes: `Ingredient.is_pantry`, `build_shopping_ingredients(..., pantry_to_buy=)`
- Produces: LLM schema + parse set `is_pantry`; template soy sauce / olive oil marked pantry

- [ ] **Step 1: Update planner prompt + JSON schema**

Replace profile-pantry prompt block with rules:

```text
Mark each ingredient with is_pantry true|false.
is_pantry true ONLY for household staples: sauces, spices, salt, pepper, sugar, stock, dried herbs/powders
(e.g. soy sauce, sweet chilli, fish sauce, cumin, paprika, garlic powder).
Fresh produce, proteins, dairy, bread, and meal-specific bulk items must be is_pantry false.
Still list pantry staples on the meal ingredients (for cooking); shopping exclusion is handled separately.
```

Remove `pantry_items_already_at_home` / old “do NOT list them” wording (or empty). Keep `assume_pantry_staples` inert or drop from prompt.

In output schema ingredients:

```json
{"name": "string", "quantity": "float", "unit": "string", "is_pantry": "bool"}
```

- [ ] **Step 2: Parse `is_pantry` in `_parse_llm_response`**

```python
Ingredient(
    name=ing["name"],
    quantity=float(ing.get("quantity", 1)),
    unit=ing.get("unit", "each"),
    is_pantry=bool(ing.get("is_pantry", False)),
)
```

- [ ] **Step 3: Template staples**

For template tuples that are staples (`soy sauce`, `olive oil`), construct `Ingredient(..., is_pantry=True)`.

- [ ] **Step 4: Orchestrator / resolver**

- `build_shopping_ingredients(plan.meals, profile, pantry_to_buy=self.state.pantry_to_buy)`
- On plan generate/swap/regenerate: `self.state.pantry_to_buy = []` and clear resolved list (if not already).
- Resolver: if `ingredient.is_pantry` and not matched in pantry_to_buy (session must pass buy list into resolve, or rely on flatten already excluding — prefer flatten-only skip so resolver rarely sees owned pantry). Remove `is_in_pantry(..., profile.pantry_items)` skip or replace with `is_owned_pantry` if ingredient still reaches resolver.

- [ ] **Step 5: Commit**

```powershell
git commit -m "Tag pantry staples in planner output and pass pantry_to_buy."
```

---

### Task 3: API `pantry_to_buy` + resolve wiring

**Files:**
- Modify: `apps/api/src/meal_agent_api/schemas.py`
- Modify: `apps/api/src/meal_agent_api/main.py`
- Modify: `packages/app-core/src/types.ts`
- Modify: `packages/app-core/src/api/client.ts`

**Interfaces:**
- Produces:
  - `POST /api/pantry/to-buy` body `{ "items": string[] }` → updates `session.state.pantry_to_buy`, clears `resolved_list` when ticks change
  - `StateResponse.pantry_to_buy: list[str]`
  - `api.setPantryToBuy(items: string[]): Promise<AppState>`

- [ ] **Step 1: Schema + endpoint**

```python
class PantryToBuyRequest(BaseModel):
    items: list[str] = Field(default_factory=list)

# StateResponse: add pantry_to_buy: list[str] = []
# from_session: pantry_to_buy=list(s.pantry_to_buy or [])
```

```python
@app.post("/api/pantry/to-buy")
async def set_pantry_to_buy(body: PantryToBuyRequest, session: AgentSession = Depends(get_session)):
    normalized = [i.strip().lower() for i in body.items if i and i.strip()]
    # dedupe preserve order
    seen = set()
    items = []
    for n in normalized:
        if n not in seen:
            seen.add(n)
            items.append(n)
    if items != list(session.state.pantry_to_buy or []):
        session.state.resolved_list = None
        session.state.products_approved = False
    session.state.pantry_to_buy = items
    return {"pantry_to_buy": items, "state": StateResponse.from_session(session)}
```

- [ ] **Step 2: Resolve uses ticks**

In `/api/shop/resolve`:

```python
ingredients = build_shopping_ingredients(
    plan.meals, profile, pantry_to_buy=list(session.state.pantry_to_buy or [])
)
```

- [ ] **Step 3: app-core types + client**

- `Meal` ingredients: add `is_pantry?: boolean`
- `AppState.pantry_to_buy: string[]`
- Keep `pantry_items` on DiscoveryAnswers as `""` for compat (unused in UI)
- `setPantryToBuy: (items: string[]) => jsonFetch("/api/pantry/to-buy", { method: "POST", body: JSON.stringify({ items }) })`

- [ ] **Step 4: Commit**

```powershell
git commit -m "Add pantry_to_buy session API and resolve wiring."
```

---

### Task 4: Web + mobile recipes UI; remove Discovery pantry

**Files:**
- Modify: `apps/web/src/steps/DiscoveryStep.tsx`
- Modify: `apps/web/src/steps/RecipesStep.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/mobile/app/discovery.tsx`
- Modify: `apps/mobile/app/recipes.tsx`
- Modify: `apps/mobile/context/AppProvider.tsx` (if resolve entry lives there)

**Interfaces:**
- Consumes: `collect`-equivalent client-side from `meal.ingredients.filter(i => i.is_pantry)`, `setPantryToBuy`, meal `Uses pantry` note

- [ ] **Step 1: Remove Discovery pantry** (web + mobile fields and review badges)

- [ ] **Step 2: RecipesStep pantry box**

Props: `pantryItems: string[]`, `pantryToBuy: string[]`, `onPantryToBuyChange: (items: string[]) => void`

UI at top of recipes:

```tsx
{pantryItems.length > 0 && (
  <Card>
    <CardHeader>
      <h2>Required pantry items</h2>
      <p className="text-sm text-slate-600">Tick to add item to shopping list</p>
    </CardHeader>
    <CardBody>
      {pantryItems.map((name) => (
        <label key={name} className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={pantryToBuy.includes(name)}
            onChange={(e) => {
              const next = e.target.checked
                ? [...pantryToBuy, name]
                : pantryToBuy.filter((x) => x !== name);
              onPantryToBuyChange(next);
            }}
          />
          <span className="capitalize">{name}</span>
        </label>
      ))}
    </CardBody>
  </Card>
)}
```

Per meal: if pantry ingredients on that meal, show `Uses pantry: …`.

- [ ] **Step 3: App.tsx wiring**

- Derive `pantryItems` from plan meals (first-seen `is_pantry` names).
- Local state synced from `state.pantry_to_buy`.
- On change: update local state; clear `shopList` cache locally.
- Before resolve / on Continue search: `await api.setPantryToBuy(pantryToBuy)` then existing resolve stream. If setPantryToBuy fails, do not resolve.

- [ ] **Step 4: Mobile parity** on `recipes.tsx` + discovery removal; same API call before build shop list.

- [ ] **Step 5: Commit**

```powershell
git commit -m "Add recipes pantry checklist and remove Discovery pantry."
```

---

### Task 5: Product rename to Meal Agent

**Files:**
- Modify: `apps/web/src/App.tsx` (h1)
- Modify: `apps/mobile/components/WizardShell.tsx`
- Modify: `apps/mobile/components/AccessCodeGate.tsx`
- Modify: `apps/mobile/app.json` (`name`)
- Modify: `apps/cli/src/meal_agent_cli/main.py` (title)
- Modify: `apps/api/src/meal_agent_api/main.py` (`FastAPI(title=...)`)
- Modify: `apps/api/src/meal_agent_api/__init__.py` docstring
- Modify: `packages/shared/src/shared/__init__.py` docstring (optional)

**Out of scope:** repo name, `woolworths_adapter`, Connect Woolworths copy, extension “Meal Agent — Woolworths Connect”.

- [ ] **Step 1: Replace user-visible “Woolworths Meal Agent” with “Meal Agent”** in the files above.

- [ ] **Step 2: Commit**

```powershell
git commit -m "Rename user-facing product to Meal Agent."
```

---

### Task 6: Regression sweep + meal-eval profile cleanup

**Files:**
- Modify: `profiles/meal_eval_baseline.json` (can leave `pantry_items` key empty string/list — unused)
- Modify tests still asserting old profile-pantry exclusion
- Smoke: `python -m pytest tests/test_pantry_opt_in.py tests/test_shop_coverage.py tests/test_meal_quality.py tests/test_heal_coverage.py -v`

- [ ] **Step 1: Fix remaining test/fixture fallout**

- [ ] **Step 2: Full targeted pytest**

```powershell
python -m pytest tests/test_pantry_opt_in.py tests/test_shop_coverage.py tests/test_meal_quality.py tests/test_heal_coverage.py tests/test_chef_plan_invalidation.py -v
```

- [ ] **Step 3: Final commit if needed**

```powershell
git commit -m "Align tests with pantry opt-in shop gate."
```

---

## Spec coverage check

| Spec requirement | Task |
|------------------|------|
| `is_pantry` on ingredients | 1, 2 |
| Session `pantry_to_buy` | 1, 3 |
| Flatten/resolve gate | 1, 2, 3 |
| LLM tag + schema | 2 |
| Discovery remove pantry | 4 |
| Recipes box + helper copy | 4 |
| Per-meal Uses pantry note | 4 |
| Tick before search | 4 |
| Cache invalidate on tick change | 3, 4 |
| CLI empty ticks | default state (1) |
| Meal Agent rename | 5 |
| Tests | 1, 6 |
