#!/usr/bin/env python3
"""Local audit: recipes-step pantry checklist completeness & sanity.

Checks against a live plan from the local API:
  1. Every is_pantry ingredient appears in collect_required_pantry (UI list)
  2. Checklist items look like staples (not protein/fresh produce/dairy/bread)
  3. Known staple names used in meals are tagged is_pantry (none missing from list)
  4. Unticked pantry items are excluded from shop flatten; ticked ones are included
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "meal_planner" / "src"))

from meal_planner.ingredients import build_shopping_ingredients  # noqa: E402
from meal_planner.pantry import collect_required_pantry  # noqa: E402
from shared.models import (  # noqa: E402
    Ingredient,
    Meal,
    MealPlan,
    MealSlot,
    MealsRequested,
    UserProfile,
)

API = "http://127.0.0.1:8000"
OUT = ROOT / "output" / "pantry-checklist-accuracy"

# Names (or substrings) that should almost always be pantry when they appear.
KNOWN_STAPLE_PATTERNS = (
    r"^salt$",
    r"^pepper$",
    r"^black pepper$",
    r"soy sauce",
    r"fish sauce",
    r"oyster sauce",
    r"teriyaki sauce",
    r"sweet chilli",
    r"sesame oil",
    r"olive oil",
    r"vegetable oil",
    r"rice vinegar",
    r"balsamic",
    r"^cumin$",
    r"^paprika$",
    r"garlic powder",
    r"onion powder",
    r"dried oregano",
    r"dried thyme",
    r"mixed herbs",
    r"curry powder",
    r"curry paste",
    r"miso paste",
    r"^sugar$",
    r"chicken stock",
    r"vegetable stock",
    r"^stock$",
    r"^honey$",  # often pantry; soft
)

# Things that must NEVER be marked pantry
NEVER_PANTRY_PATTERNS = (
    r"chicken",
    r"beef",
    r"pork",
    r"lamb",
    r"salmon",
    r"mince",
    r"tofu",
    r"milk",
    r"cream",
    r"yoghurt",
    r"yogurt",
    r"butter",
    r"cheese",
    r"bread",
    r"wrap",
    r"tortilla",
    r"pasta\b",
    r"\brice\b",
    r"noodle",
    r"potato",
    r"tomato",
    r"carrot",
    r"broccoli",
    r"capsicum",
    r"onion",
    r"garlic$",  # fresh garlic bulb — powder OK
    r"lettuce",
    r"spinach",
    r"cucumber",
    r"avocado",
    r"egg",
)


def sse(client: httpx.Client, method: str, path: str, *, timeout: float = 420.0) -> dict:
    complete = None
    errors: list[str] = []
    with client.stream(method, path, timeout=timeout) as resp:
        resp.raise_for_status()
        event = "message"
        data: list[str] = []
        for raw in resp.iter_lines():
            line = raw.decode() if isinstance(raw, bytes) else raw
            if line == "":
                if data:
                    payload = json.loads("\n".join(data))
                    if event == "status":
                        print(" ", payload.get("message") if isinstance(payload, dict) else payload)
                    elif event == "complete":
                        complete = payload
                    elif event == "error":
                        errors.append(str(payload))
                event = "message"
                data = []
                continue
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip())
    if errors and not complete:
        raise RuntimeError("; ".join(errors))
    if not complete:
        raise RuntimeError(f"no complete for {path}")
    return complete


def _meal_models(plan: dict) -> list[Meal]:
    meals: list[Meal] = []
    for m in plan.get("meals") or []:
        try:
            slot = MealSlot(str(m.get("slot") or "dinner").lower())
        except ValueError:
            slot = MealSlot.DINNER
        ings = [
            Ingredient(
                name=str(i.get("name") or ""),
                quantity=float(i.get("quantity") or 1),
                unit=str(i.get("unit") or "each"),
                is_pantry=bool(i.get("is_pantry", False)),
            )
            for i in (m.get("ingredients") or [])
            if i.get("name")
        ]
        meals.append(
            Meal(
                name=str(m.get("name") or ""),
                slot=slot,
                day_label=str(m.get("day_label") or ""),
                description=str(m.get("description") or ""),
                ingredients=ings,
                steps=[str(s) for s in (m.get("steps") or [])],
            )
        )
    return meals


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, name, re.I) for p in patterns)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []

    with httpx.Client(base_url=API, timeout=120.0, follow_redirects=True) as client:
        r = client.post("/api/session/start")
        r.raise_for_status()
        sid = r.json()["session_id"]
        client.headers["X-Session-Id"] = sid
        print("session", sid[:8])

        answers = {
            "adults": 2,
            "children_under_13": 0,
            "children_age_bands": {"1-3": 0, "4-6": 0, "7-9": 0, "10-12": 0},
            "household_size": 2,
            "days": 5,
            "dinner_count": 3,
            "lunch_count": 1,
            "snack_count": 0,
            "allergies": "",
            "mandatory_items": "",
            "pantry_items": "",
            "likes": "chicken, vegetables, pasta, rice, asian",
            "dislikes": "lamb",
            "other_instructions": "Use soy sauce and common spices.",
            "budget_nzd": 140.0,
            "store_name": "",
            "simplicity": "simple",
            "brand_preference": "mixed",
            "chef_id": "basic_sam",
            "lunch_mode": "practical",
        }
        client.post("/api/profile", json=answers).raise_for_status()
        print("plan…")
        payload = sse(client, "POST", "/api/plan/generate")
        plan = payload.get("meal_plan") or {}
        (OUT / "meal_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    meals = _meal_models(plan)
    checklist = collect_required_pantry(meals)

    # Rebuild checklist the same way the web UI does (first-seen lowercased names)
    ui_list: list[str] = []
    seen: set[str] = set()
    all_pantry_ings: list[str] = []
    all_ings: list[tuple[str, bool]] = []
    for meal in meals:
        for ing in meal.ingredients:
            all_ings.append((ing.name, ing.is_pantry))
            if not ing.is_pantry:
                continue
            name = ing.name.strip().lower()
            all_pantry_ings.append(name)
            if name and name not in seen:
                seen.add(name)
                ui_list.append(name)

    print("\n=== REQUIRED PANTRY CHECKLIST (UI) ===")
    for name in ui_list:
        print(f"  [ ] {name}")
    if not ui_list:
        print("  (empty)")

    print("\n=== PER-MEAL PANTRY NOTES ===")
    for meal in meals:
        tagged = [i.name for i in meal.ingredients if i.is_pantry]
        print(f"  {meal.day_label} {meal.slot.value}: {meal.name}")
        print(f"    pantry={tagged or '—'}")

    # 1) collect_required_pantry matches UI list
    if checklist != ui_list:
        issues.append(f"collect_required_pantry mismatch: {checklist} vs ui {ui_list}")

    # 2) every is_pantry ingredient is on the checklist
    for name in all_pantry_ings:
        if name not in seen:
            issues.append(f"pantry ingredient missing from checklist: {name}")

    # 3) checklist items must not look like shop-fresh / protein
    for name in ui_list:
        if _matches_any(name, NEVER_PANTRY_PATTERNS):
            # allow "garlic powder" / "onion powder"
            if "powder" in name or "sauce" in name or "oil" in name or "paste" in name:
                continue
            if name in {"garlic powder", "onion powder"}:
                continue
            issues.append(f"nonsensical pantry tick item: {name}")

    # 4) known staples used in meals must be tagged (appear on checklist)
    for name, is_pantry in all_ings:
        if not _matches_any(name, KNOWN_STAPLE_PATTERNS):
            continue
        if not is_pantry:
            issues.append(f"staple not tagged is_pantry (missing from checklist): {name}")

    # 5) shop flatten gate
    profile = UserProfile(
        household_size=2,
        meals_requested=MealsRequested(dinner=3, lunch=1),
        budget_nzd=140,
    )
    shop_default = {i.name for i in build_shopping_ingredients(meals, profile, pantry_to_buy=[])}
    for name in ui_list:
        if name in shop_default:
            issues.append(f"unticked pantry still on shop list: {name}")
    if ui_list:
        shop_ticked = {
            i.name
            for i in build_shopping_ingredients(meals, profile, pantry_to_buy=list(ui_list))
        }
        for name in ui_list:
            if name not in shop_ticked:
                issues.append(f"ticked pantry missing from shop list: {name}")

    summary = {
        "checklist": ui_list,
        "meal_count": len(meals),
        "issues": issues,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"\n=== ISSUES ({len(issues)}) ===")
    for i in issues:
        print(" -", i)
    if issues:
        print(f"FAIL -> {OUT}")
        return 2
    print(f"PASS -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
