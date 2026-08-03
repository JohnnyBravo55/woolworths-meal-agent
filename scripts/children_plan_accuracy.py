#!/usr/bin/env python3
"""Local audit: children prefs → chef portions + kid-suitable meals.

Generates meal plans for several adult/child age-band combinations and checks:
  A) Protein/carb dinner portions scale sensibly with adult_equivalent_servings
  B) No clearly unsuitable-for-children meals when children_under_13 > 0
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

from meal_planner.meal_quality import kid_unsuitable_reasons  # noqa: E402
from shared.models import Ingredient, Meal, MealSlot  # noqa: E402
from shared.portions import adult_equivalent_servings  # noqa: E402

API = "http://127.0.0.1:8000"
OUT = ROOT / "output" / "children-plan-accuracy"

# Per adult-equivalent dinner protein (g) — household-sane band for NZ home cooking.
# Upper bound allows practical-lunch leftover bump (~1.5× on feeding dinners).
PROTEIN_G_PER_AE_MIN = 70
PROTEIN_G_PER_AE_MAX = 320
# Carb staples (rice/pasta dry-ish) per AE dinner
CARB_G_PER_AE_MIN = 40
CARB_G_PER_AE_MAX = 320

PROTEIN_RE = re.compile(
    r"\b(chicken|beef|pork|lamb|mince|salmon|fish|tofu|turkey|prawn|bacon|steak)\b",
    re.I,
)
CARB_RE = re.compile(
    r"\b(rice|pasta|noodle|noodles|potato|potatoes|bread|wrap|tortilla|couscous|quinoa)\b",
    re.I,
)

SCENARIOS: list[dict] = [
    {
        "id": "baseline_2a",
        "adults": 2,
        "children_under_13": 0,
        "children_age_bands": {"1-3": 0, "4-6": 0, "7-9": 0, "10-12": 0},
        "chef_id": "basic_sam",
        "expect_kids": False,
    },
    {
        "id": "2a_1toddler",
        "adults": 2,
        "children_under_13": 1,
        "children_age_bands": {"1-3": 1, "4-6": 0, "7-9": 0, "10-12": 0},
        "chef_id": "basic_sam",
        "expect_kids": True,
    },
    {
        "id": "2a_1preschool",
        "adults": 2,
        "children_under_13": 1,
        "children_age_bands": {"1-3": 0, "4-6": 1, "7-9": 0, "10-12": 0},
        "chef_id": "basic_sam",
        "expect_kids": True,
    },
    {
        "id": "2a_2kids_mixed",
        "adults": 2,
        "children_under_13": 2,
        "children_age_bands": {"1-3": 0, "4-6": 1, "7-9": 1, "10-12": 0},
        "chef_id": "basic_sam",
        "expect_kids": True,
    },
    {
        "id": "2a_2tweens",
        "adults": 2,
        "children_under_13": 2,
        "children_age_bands": {"1-3": 0, "4-6": 0, "7-9": 0, "10-12": 2},
        "chef_id": "basic_sam",
        "expect_kids": True,
    },
    {
        "id": "1a_2toddlers",
        "adults": 1,
        "children_under_13": 2,
        "children_age_bands": {"1-3": 2, "4-6": 0, "7-9": 0, "10-12": 0},
        "chef_id": "basic_sam",
        "expect_kids": True,
    },
    {
        "id": "2a_3kids_spread",
        "adults": 2,
        "children_under_13": 3,
        "children_age_bands": {"1-3": 1, "4-6": 1, "7-9": 1, "10-12": 0},
        "chef_id": "basic_sam",
        "expect_kids": True,
    },
    {
        "id": "2a_kids_kenji",
        "adults": 2,
        "children_under_13": 2,
        "children_age_bands": {"1-3": 0, "4-6": 0, "7-9": 1, "10-12": 1},
        "chef_id": "premium_kenji",
        "expect_kids": True,
    },
]


def sse(client: httpx.Client, method: str, path: str, *, timeout: float = 420.0, json_body=None) -> dict:
    complete = None
    errors: list[str] = []
    with client.stream(method, path, json=json_body, timeout=timeout) as resp:
        resp.raise_for_status()
        event = "message"
        data: list[str] = []
        for raw in resp.iter_lines():
            line = raw.decode() if isinstance(raw, bytes) else raw
            if line == "":
                if data:
                    payload = json.loads("\n".join(data))
                    if event == "status":
                        msg = payload.get("message") if isinstance(payload, dict) else payload
                        print("   ", msg)
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


def _to_grams(qty: float, unit: str) -> float | None:
    u = (unit or "").lower().strip()
    if u in {"g", "gram", "grams"}:
        return float(qty)
    if u in {"kg", "kilogram", "kilograms", "kilo"}:
        return float(qty) * 1000.0
    return None


def _as_meal_model(meal: dict) -> Meal:
    slot_raw = str(meal.get("slot") or "dinner").lower()
    try:
        slot = MealSlot(slot_raw)
    except ValueError:
        slot = MealSlot.DINNER
    ingredients = [
        Ingredient(
            name=str(i.get("name") or "item"),
            quantity=float(i.get("quantity") or 1),
            unit=str(i.get("unit") or "each"),
        )
        for i in (meal.get("ingredients") or [])
    ]
    return Meal(
        name=str(meal.get("name") or ""),
        slot=slot,
        day_label=str(meal.get("day_label") or ""),
        description=str(meal.get("description") or ""),
        ingredients=ingredients,
        steps=[str(s) for s in (meal.get("steps") or [])],
    )


def protein_grams_for_meal(meal: dict) -> float:
    total = 0.0
    for ing in meal.get("ingredients") or []:
        name = str(ing.get("name") or "")
        if not PROTEIN_RE.search(name):
            continue
        g = _to_grams(float(ing.get("quantity") or 0), str(ing.get("unit") or ""))
        if g is not None:
            total += g
        else:
            # Fillet/each heuristics: ~150g each for chicken/fish pieces
            unit = str(ing.get("unit") or "").lower()
            if unit in {"each", "fillet", "fillets", "piece", "pieces"}:
                total += float(ing.get("quantity") or 0) * 150.0
    return total


def carb_grams_for_meal(meal: dict) -> float:
    total = 0.0
    for ing in meal.get("ingredients") or []:
        name = str(ing.get("name") or "")
        if not CARB_RE.search(name):
            continue
        g = _to_grams(float(ing.get("quantity") or 0), str(ing.get("unit") or ""))
        if g is not None:
            total += g
        else:
            unit = str(ing.get("unit") or "").lower()
            qty = float(ing.get("quantity") or 0)
            if "potato" in name.lower() and unit in {"each", "piece", "pieces"}:
                total += qty * 180.0
            elif any(x in name.lower() for x in ("wrap", "tortilla", "bread")):
                total += qty * 40.0
    return total


def audit_scenario(client: httpx.Client, scenario: dict) -> dict:
    adults = int(scenario["adults"])
    children = int(scenario["children_under_13"])
    bands = scenario["children_age_bands"]
    expected_ae = adult_equivalent_servings(adults, bands)

    answers = {
        "adults": adults,
        "children_under_13": children,
        "children_age_bands": bands,
        "household_size": adults + children,
        "days": 5,
        "dinner_count": 3,
        "lunch_count": 1,
        "snack_count": 0,
        "allergies": "",
        "mandatory_items": "milk",
        "pantry_items": "salt, pepper, olive oil, garlic, onions",
        "likes": "chicken, vegetables, pasta, rice",
        "dislikes": "lamb, organ meat",
        "other_instructions": "Family meals; keep it simple.",
        "budget_nzd": 140.0 + 20.0 * children,
        "store_name": "Christchurch Central",
        "simplicity": "simple",
        "brand_preference": "mixed",
        "chef_id": scenario["chef_id"],
        "lunch_mode": "practical",
    }

    issues: list[str] = []
    r = client.post("/api/session/start")
    r.raise_for_status()
    sid = r.json()["session_id"]
    client.headers["X-Session-Id"] = sid

    pr = client.post("/api/profile", json=answers)
    if pr.status_code >= 400:
        issues.append(f"profile rejected: {pr.status_code} {pr.text[:300]}")
        return {
            "id": scenario["id"],
            "expected_ae": expected_ae,
            "issues": issues,
            "meals": [],
        }
    payload = pr.json()
    profile = payload.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    state_profile = ((payload.get("state") or {}).get("profile")) or {}
    if isinstance(state_profile, dict):
        for key in (
            "adult_equivalent_servings",
            "adults",
            "children_under_13",
            "children_age_bands",
            "household_size",
        ):
            if key not in profile and key in state_profile:
                profile[key] = state_profile[key]

    if "adult_equivalent_servings" not in profile:
        issues.append(
            "profile missing adult_equivalent_servings "
            "(API may be running stale shared package — restart meal-agent-api)"
        )
    ae = float(profile.get("adult_equivalent_servings") or expected_ae)
    if "adult_equivalent_servings" in profile and abs(ae - expected_ae) > 0.01:
        issues.append(f"AE mismatch: profile={ae} expected={expected_ae}")

    hh = int(profile.get("household_size") or 0)
    if hh and hh != adults + children:
        issues.append(f"household_size={hh} expected={adults + children}")
    if scenario["expect_kids"] and int(profile.get("children_under_13") or 0) < 1:
        issues.append("children_under_13 not persisted on profile")

    print(f"\n=== {scenario['id']} adults={adults} kids={children} AE={expected_ae} chef={scenario['chef_id']} ===")
    plan_payload = sse(client, "POST", "/api/plan/generate")
    plan = plan_payload.get("meal_plan") or {}
    meals = list(plan.get("meals") or [])
    dinners = [m for m in meals if str(m.get("slot") or "").lower() == "dinner"]

    meal_rows: list[dict] = []
    protein_per_ae: list[float] = []
    for meal in dinners:
        p_g = protein_grams_for_meal(meal)
        c_g = carb_grams_for_meal(meal)
        p_ae = p_g / ae if ae > 0 else 0
        c_ae = c_g / ae if ae > 0 else 0
        if p_g > 0:
            protein_per_ae.append(p_ae)
        row = {
            "name": meal.get("name"),
            "protein_g": round(p_g, 1),
            "carb_g": round(c_g, 1),
            "protein_g_per_ae": round(p_ae, 1),
            "carb_g_per_ae": round(c_ae, 1),
        }
        meal_rows.append(row)
        print(
            f"  dinner: {meal.get('name')}  protein={p_g:.0f}g ({p_ae:.0f}/AE)  "
            f"carb={c_g:.0f}g ({c_ae:.0f}/AE)"
        )

        if p_g > 0 and (p_ae < PROTEIN_G_PER_AE_MIN or p_ae > PROTEIN_G_PER_AE_MAX):
            issues.append(
                f"portion protein odd for '{meal.get('name')}': "
                f"{p_ae:.0f}g/AE (want {PROTEIN_G_PER_AE_MIN}-{PROTEIN_G_PER_AE_MAX})"
            )
        if c_g > 0 and (c_ae < CARB_G_PER_AE_MIN or c_ae > CARB_G_PER_AE_MAX):
            issues.append(
                f"portion carb odd for '{meal.get('name')}': "
                f"{c_ae:.0f}g/AE (want {CARB_G_PER_AE_MIN}-{CARB_G_PER_AE_MAX})"
            )

        # If kids present, headcount oversizing: protein sized as if every child were a full adult
        if scenario["expect_kids"] and ae + 0.5 < hh and p_g > 0:
            per_head = p_g / hh
            # If per-head is still in adult band AND AE is much smaller, likely oversize
            if per_head >= PROTEIN_G_PER_AE_MIN and p_ae > PROTEIN_G_PER_AE_MAX * 0.95:
                issues.append(
                    f"likely sized to headcount not AE for '{meal.get('name')}': "
                    f"{p_g:.0f}g for HH={hh} AE={ae}"
                )

    if scenario["expect_kids"]:
        for meal in meals:
            reasons = kid_unsuitable_reasons(_as_meal_model(meal))
            for label in reasons:
                issues.append(f"unsuitable ({label}) in '{meal.get('name')}'")

    # Baseline (no kids) should still produce dinners
    if not dinners:
        issues.append("no dinners in plan")

    return {
        "id": scenario["id"],
        "adults": adults,
        "children": children,
        "bands": bands,
        "expected_ae": expected_ae,
        "profile_ae": ae,
        "chef_id": scenario["chef_id"],
        "meals": meal_rows,
        "all_meal_names": [m.get("name") for m in meals],
        "avg_protein_g_per_ae": round(sum(protein_per_ae) / len(protein_per_ae), 1)
        if protein_per_ae
        else None,
        "issues": issues,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    all_issues: list[str] = []

    with httpx.Client(base_url=API, timeout=120.0, follow_redirects=True) as client:
        for scenario in SCENARIOS:
            try:
                result = audit_scenario(client, scenario)
            except Exception as exc:  # noqa: BLE001
                result = {
                    "id": scenario["id"],
                    "issues": [f"hard error: {exc}"],
                    "meals": [],
                }
            results.append(result)
            for issue in result.get("issues") or []:
                all_issues.append(f"[{result['id']}] {issue}")

    summary = {
        "scenarios": len(results),
        "issue_count": len(all_issues),
        "results": results,
        "issues": all_issues,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("\n=== SUMMARY ===")
    for r in results:
        status = "PASS" if not r.get("issues") else "FAIL"
        print(
            f"  {status} {r['id']}: AE={r.get('expected_ae')} "
            f"avg_protein/AE={r.get('avg_protein_g_per_ae')} "
            f"issues={len(r.get('issues') or [])}"
        )
        for issue in r.get("issues") or []:
            print(f"    - {issue}")

    if all_issues:
        print(f"\nFAIL ({len(all_issues)} issues) -> {OUT}")
        return 2
    print(f"\nPASS -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
