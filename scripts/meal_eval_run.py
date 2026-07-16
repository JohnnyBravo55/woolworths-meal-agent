#!/usr/bin/env python3
"""Drive one meal-eval customer run against local meal-agent-api and audit plan vs shop/cart.

Usage:
  python scripts/meal_eval_run.py --run-index 1 --chef basic_sam
  python scripts/meal_eval_run.py --run-index 1 --cart
  python scripts/meal_eval_run.py --audit-only output/meal-eval/run-001-basic_sam
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "profiles" / "meal_eval_baseline.json"
DEFAULT_OUT = ROOT / "output" / "meal-eval"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"

CHEF_ORDER = [
    "basic_sam",
    "premium_elena",
    "premium_kenji",
    "premium_moana",
    "premium_alex",
    "premium_amara",
]

WRONG_PRODUCT_HINTS: dict[str, tuple[str, ...]] = {
    "capsicum": ("hummus", "dip"),
    "cucumber": ("drink", "mixer", "yoghurt dip", "yogurt"),
    "blueberries": ("choc", "chocolate"),
    "apple": ("puree", "pouch"),
    "apples": ("puree", "pouch"),
    "beef strips": ("dog", "pet", "treat"),
    "chicken breast": ("shredded roast", "dog", "pet"),
}

LEFTOVER_WORDS = ("leftover", "yesterday", "reuse", "reheat")
LEFTOVER_PHRASES = ("left over", "left-over", "extra from", "extra dinner")

ALLERGY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "gluten": ("wheat", "gluten", "barley", "rye", "breadcrumbs", "couscous"),
    "dairy": ("milk", "cheese", "butter", "cream", "yoghurt", "yogurt"),
    "nut": ("almond", "cashew", "walnut", "peanut", "pistachio", "hazelnut"),
    "peanut": ("peanut",),
    "egg": ("egg",),
    "soy": ("soy", "soya"),
    "shellfish": ("prawn", "shrimp", "crab", "lobster", "mussel", "oyster"),
}


def chef_for_index(run_index: int, pinned: str | None) -> str:
    if pinned:
        return pinned
    return CHEF_ORDER[(run_index - 1) % len(CHEF_ORDER)]


def load_baseline(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("name", None)
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_sse_stream(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_name = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = "message"
            return
        raw = "\n".join(data_lines)
        data_lines = []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        events.append((event_name, payload if isinstance(payload, dict) else {"value": payload}))
        event_name = "message"

    for line in response.iter_lines():
        if line is None:
            continue
        if line == "":
            flush()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
            continue
    flush()
    return events


def consume_sse(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    timeout: float,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Return (complete_payload, warnings, errors)."""
    warnings: list[str] = []
    errors: list[str] = []
    complete: dict[str, Any] | None = None
    with client.stream(method, path, timeout=timeout) as response:
        if response.status_code >= 400:
            body = response.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {body}")
        for event_name, payload in parse_sse_stream(response):
            if event_name == "warning":
                warnings.append(str(payload.get("message") or payload))
            elif event_name == "error":
                errors.append(str(payload.get("message") or payload))
            elif event_name == "complete":
                complete = payload
    return complete, warnings, errors


def _norm(s: str) -> str:
    return s.lower().strip()


def _in_pantry(name: str, pantry: list[str]) -> bool:
    n = _norm(name)
    for p in pantry:
        p = _norm(p)
        if p and (p in n or n in p):
            return True
    return False


def _is_leftover_meal(meal: dict[str, Any]) -> bool:
    text = f"{meal.get('name', '')} {meal.get('description', '')} {' '.join(meal.get('steps') or [])}".lower()
    if any(p in text for p in LEFTOVER_PHRASES):
        return True
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in LEFTOVER_WORDS)


def _allergy_tokens(allergies: list[str] | str) -> list[tuple[str, tuple[str, ...]]]:
    if isinstance(allergies, str):
        parts = [a.strip().lower() for a in allergies.split(",") if a.strip()]
    else:
        parts = [str(a).strip().lower() for a in allergies if str(a).strip()]
    out: list[tuple[str, tuple[str, ...]]] = []
    for part in parts:
        for key, kws in ALLERGY_KEYWORDS.items():
            if key in part or part in key:
                out.append((part, kws))
                break
        else:
            out.append((part, (part,)))
    return out


def run_heuristic_audit(
    profile: dict[str, Any],
    meal_plan: dict[str, Any],
    resolved: dict[str, Any],
) -> dict[str, Any]:
    """Recipe-vs-shop heuristics (aligned with output/_audit_run.py)."""
    pantry_raw = profile.get("pantry_items") or []
    if isinstance(pantry_raw, str):
        pantry = [p.strip() for p in pantry_raw.split(",") if p.strip()]
    else:
        pantry = [str(p) for p in pantry_raw]

    items = list(resolved.get("items") or [])
    shop_by_ing = {_norm(i.get("ingredient", "")): i for i in items}
    shop_links: dict[str, list[dict[str, Any]]] = {}
    for i in items:
        for m in i.get("for_meals") or []:
            shop_links.setdefault(m, []).append(i)

    def find_line(name: str) -> dict[str, Any] | None:
        try:
            from meal_planner.ingredient_normalize import normalize_ingredient_name

            key = _norm(normalize_ingredient_name(name))
        except Exception:  # noqa: BLE001
            key = _norm(name)
        if key in shop_by_ing:
            return shop_by_ing[key]
        # Also try raw name (pre-normalize) for fuzzy contains match
        raw = _norm(name)
        if raw in shop_by_ing:
            return shop_by_ing[raw]
        for candidate in (key, raw):
            hit = next(
                (shop_by_ing[k] for k in shop_by_ing if candidate in k or k in candidate),
                None,
            )
            if hit:
                return hit
        return None

    gaps: list[dict[str, str]] = []
    wrong_product: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    covered = 0
    manual_ok = 0

    for meal in meal_plan.get("meals") or []:
        meal_name = meal.get("name", "")
        slot = meal.get("slot", "")
        day = meal.get("day_label", "")
        leftover = _is_leftover_meal(meal)
        linked = shop_links.get(meal_name, [])
        linked_non_mandatory = [i for i in linked if not i.get("is_mandatory")]

        for ing in meal.get("ingredients") or []:
            name = ing.get("name", "")
            lower = _norm(name)
            if _in_pantry(name, pantry):
                continue
            if leftover and lower.startswith(("leftover ", "left over ", "left-over ", "steamed ")):
                continue

            line = find_line(name)
            if not line and lower == "cooked chicken":
                line = find_line("chicken breast")
            if not line and lower == "cooked rice":
                line = find_line("rice")

            # Leftover protein/starch reused from dinner — never a shop gap
            if leftover:
                try:
                    from meal_planner.meal_quality import leftover_meal_needs_shop

                    if not leftover_meal_needs_shop(name):
                        covered += 1
                        continue
                except Exception:  # noqa: BLE001
                    pass

            if line:
                product = str(line.get("product_name") or "")
                linked_to = meal_name in (line.get("for_meals") or [])
                if line.get("cart_blocked"):
                    blocked.append(
                        {
                            "day": day,
                            "meal": meal_name,
                            "ingredient": name,
                            "detail": str(line.get("block_reason") or "blocked"),
                        }
                    )
                elif line.get("sku") == "OFFLINE":
                    manual_ok += 1
                    if not linked_to:
                        gaps.append(
                            {
                                "day": day,
                                "meal": meal_name,
                                "ingredient": name,
                                "detail": "not linked",
                            }
                        )
                else:
                    hints = WRONG_PRODUCT_HINTS.get(lower) or WRONG_PRODUCT_HINTS.get(
                        lower.rstrip("s")
                    )
                    if hints and any(h in product.lower() for h in hints):
                        wrong_product.append(
                            {
                                "day": day,
                                "meal": meal_name,
                                "ingredient": name,
                                "product": product,
                            }
                        )
                    elif not linked_to:
                        gaps.append(
                            {
                                "day": day,
                                "meal": meal_name,
                                "ingredient": name,
                                "detail": "on list but not linked",
                            }
                        )
                    else:
                        covered += 1
            else:
                gaps.append(
                    {
                        "day": day,
                        "meal": meal_name,
                        "ingredient": name,
                        "detail": "missing",
                    }
                )

        if (
            not leftover
            and slot in ("dinner", "lunch", "breakfast")
            and not linked_non_mandatory
        ):
            need = [
                ing
                for ing in (meal.get("ingredients") or [])
                if not _in_pantry(ing.get("name", ""), pantry)
                and "leftover" not in _norm(ing.get("name", ""))
            ]
            if need:
                gaps.append(
                    {
                        "day": day,
                        "meal": meal_name,
                        "ingredient": "(meal)",
                        "detail": "orphan — no shop lines",
                    }
                )

    allergy_hits: list[dict[str, str]] = []
    allergy_source = profile.get("allergies") or []
    for allergy, keywords in _allergy_tokens(allergy_source):
        for item in items:
            blob = f"{item.get('ingredient', '')} {item.get('product_name', '')}".lower()
            if any(k in blob for k in keywords):
                # Allow explicit gluten-free products when allergy is gluten
                if allergy == "gluten" and "gluten free" in blob:
                    continue
                allergy_hits.append(
                    {
                        "allergy": allergy,
                        "ingredient": str(item.get("ingredient") or ""),
                        "product": str(item.get("product_name") or ""),
                    }
                )

    mandatory_raw = profile.get("mandatory_items") or []
    if isinstance(mandatory_raw, str):
        mandatory = [m.strip().lower() for m in mandatory_raw.split(",") if m.strip()]
    else:
        mandatory = [str(m).strip().lower() for m in mandatory_raw if str(m).strip()]

    shop_names = {_norm(i.get("ingredient", "")) for i in items}
    missing_mandatory: list[str] = []
    for m in mandatory:
        if not any(m in s or s in m for s in shop_names):
            # also accept product_name match
            if not any(m in _norm(i.get("product_name", "")) for i in items):
                missing_mandatory.append(m)

    return {
        "covered": covered,
        "manual_ok": manual_ok,
        "gaps": gaps,
        "blocked": blocked,
        "wrong_product": wrong_product,
        "allergy_hits": allergy_hits,
        "missing_mandatory": missing_mandatory,
        "coverage_issues": list(resolved.get("coverage_issues") or []),
        "unresolved_ingredients": list(resolved.get("unresolved_ingredients") or []),
    }


def run_shop_coverage_audit(
    profile_obj: Any,
    meal_plan_obj: Any,
    resolved: dict[str, Any],
) -> list[dict[str, Any]]:
    from meal_planner.shop_coverage import audit_shop_coverage
    from shared.models import Ingredient

    items = [
        Ingredient(
            name=str(i.get("ingredient") or ""),
            quantity=float(i.get("quantity") or 1),
            unit=str(i.get("unit") or "each").lower(),
            for_meals=list(i.get("for_meals") or []),
            is_mandatory=bool(i.get("is_mandatory")),
        )
        for i in (resolved.get("items") or [])
        if i.get("ingredient")
    ]
    issues = audit_shop_coverage(meal_plan_obj.meals, items, profile_obj)
    return [
        {
            "meal_name": iss.meal_name,
            "day_label": iss.day_label,
            "slot": str(iss.slot),
            "kind": iss.kind,
            "detail": iss.detail,
            "missing_ingredients": list(iss.missing_ingredients),
        }
        for iss in issues
    ]


def run_budget_cart_audit(
    resolved: dict[str, Any],
    cart_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assess (a) budget, (b) trolley add success, plus offline/blocked blockers."""
    items = list(resolved.get("items") or [])
    total = float(resolved.get("total") or 0)
    budget = float(resolved.get("budget_nzd") or 0)
    within_budget_flag = bool(resolved.get("within_budget"))
    # Prefer total vs budget (includes OFFLINE estimates) when assessing spend
    within_budget = total <= budget if budget > 0 else within_budget_flag

    def _is_leftover_label(name: str) -> bool:
        n = str(name or "").lower().strip()
        return n.startswith(("leftover ", "left over ", "left-over ", "steamed "))

    offline = [
        i
        for i in items
        if i.get("sku") == "OFFLINE" and not _is_leftover_label(i.get("ingredient", ""))
    ]
    blocked = [i for i in items if i.get("cart_blocked")]
    addable = [
        i
        for i in items
        if i.get("sku") != "OFFLINE" and i.get("in_stock", True) and not i.get("cart_blocked")
    ]

    cart_issues: list[dict[str, Any]] = []
    if cart_result is None:
        trolley_ok = False
        cart_issues.append({"kind": "cart_not_run", "detail": "No cart_result.json — cart step skipped or failed"})
        success_count = failure_count = skipped_offline = 0
        cart_errors: list[str] = []
        session_lost = False
        added_total = 0.0
        cart_subtotal = None
    else:
        success_count = int(cart_result.get("success_count") or 0)
        failure_count = int(cart_result.get("failure_count") or 0)
        skipped_offline = int(cart_result.get("skipped_offline") or 0)
        cart_errors = [
            e
            for e in list(cart_result.get("errors") or [])
            if "leftover " not in str(e).lower()
        ]
        session_lost = bool(cart_result.get("session_lost"))
        added_total = float(cart_result.get("added_total") or 0)
        cart_subtotal = cart_result.get("cart_subtotal")

        if session_lost:
            cart_issues.append(
                {"kind": "session_lost", "detail": "Woolworths session lost during cart add"}
            )
        if failure_count > 0:
            cart_issues.append(
                {
                    "kind": "cart_failures",
                    "detail": f"{failure_count} cart add failure(s)",
                    "errors": cart_errors,
                }
            )
        elif cart_errors:
            cart_issues.append({"kind": "cart_errors", "detail": "; ".join(cart_errors)})

        # Every addable line should land in the trolley
        if success_count < len(addable):
            cart_issues.append(
                {
                    "kind": "incomplete_trolley",
                    "detail": (
                        f"Added {success_count}/{len(addable)} addable items "
                        f"(offline={len(offline)}, blocked={len(blocked)})"
                    ),
                }
            )
        trolley_ok = (
            failure_count == 0
            and not session_lost
            and success_count >= len(addable)
            and len(addable) > 0
            and len(offline) == 0
            and len(blocked) == 0
        )

    if offline:
        cart_issues.append(
            {
                "kind": "offline_items",
                "detail": f"{len(offline)} item(s) could not resolve to Woolworths SKUs",
                "ingredients": [i.get("ingredient") for i in offline],
            }
        )
    if blocked:
        cart_issues.append(
            {
                "kind": "blocked_items",
                "detail": f"{len(blocked)} item(s) cart-blocked (wrong/unsafe match)",
                "ingredients": [
                    {"ingredient": i.get("ingredient"), "reason": i.get("block_reason")}
                    for i in blocked
                ],
            }
        )
    if not within_budget:
        cart_issues.append(
            {
                "kind": "over_budget",
                "detail": f"Shop total ${total:.2f} exceeds budget ${budget:.2f}",
            }
        )

    return {
        "within_budget": within_budget,
        "total": total,
        "budget_nzd": budget,
        "addable_count": len(addable),
        "offline_count": len(offline),
        "blocked_count": len(blocked),
        "trolley_ok": trolley_ok,
        "success_count": success_count,
        "failure_count": failure_count,
        "skipped_offline": skipped_offline,
        "added_total": added_total,
        "cart_subtotal": cart_subtotal,
        "session_lost": session_lost,
        "cart_errors": cart_errors,
        "cart_issues": cart_issues,
    }


def build_audit_report(
    *,
    run_index: int,
    chef_id: str,
    heuristic: dict[str, Any],
    coverage: list[dict[str, Any]],
    cart_audit: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    product_issue_count = (
        len(heuristic["gaps"])
        + len(heuristic["wrong_product"])
        + len(heuristic["blocked"])
        + len(heuristic["allergy_hits"])
        + len(heuristic["missing_mandatory"])
        + len(heuristic["coverage_issues"])
        + len(coverage)
    )
    cart_issue_count = len((cart_audit or {}).get("cart_issues") or [])
    issue_count = product_issue_count + cart_issue_count
    findings = {
        "run_index": run_index,
        "chef_id": chef_id,
        "passed": issue_count == 0,
        "issue_count": issue_count,
        "shop_coverage": coverage,
        "heuristic": heuristic,
        "cart_audit": cart_audit,
        "checks": {
            "products_ok": product_issue_count == 0,
            "within_budget": None if cart_audit is None else bool(cart_audit.get("within_budget")),
            "trolley_ok": None if cart_audit is None else bool(cart_audit.get("trolley_ok")),
        },
    }

    lines = [
        f"# Meal-eval audit — run {run_index:03d} ({chef_id})",
        "",
        f"**Result:** {'PASS' if findings['passed'] else 'FAIL'} ({issue_count} issue(s))",
        "",
        "## Checks",
        "",
        f"- **(c) Products correct:** {'PASS' if findings['checks']['products_ok'] else 'FAIL'}",
    ]
    if cart_audit is not None:
        lines.append(
            f"- **(a) Within budget:** {'PASS' if cart_audit.get('within_budget') else 'FAIL'} "
            f"(${cart_audit.get('total', 0):.2f} / ${cart_audit.get('budget_nzd', 0):.2f})"
        )
        lines.append(
            f"- **(b) Trolley add:** {'PASS' if cart_audit.get('trolley_ok') else 'FAIL'} "
            f"(added {cart_audit.get('success_count', 0)}/"
            f"{cart_audit.get('addable_count', 0)} addable; "
            f"failures={cart_audit.get('failure_count', 0)}; "
            f"offline={cart_audit.get('offline_count', 0)}; "
            f"blocked={cart_audit.get('blocked_count', 0)})"
        )
    else:
        lines.append("- **(a) Within budget:** _not assessed (shop-only run)_")
        lines.append("- **(b) Trolley add:** _not assessed (shop-only run)_")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Covered ingredient links: {heuristic['covered']}",
            f"- Manual/offline OK: {heuristic['manual_ok']}",
            f"- Gaps: {len(heuristic['gaps'])}",
            f"- Wrong product: {len(heuristic['wrong_product'])}",
            f"- Blocked: {len(heuristic['blocked'])}",
            f"- Allergy hits: {len(heuristic['allergy_hits'])}",
            f"- Missing mandatory: {len(heuristic['missing_mandatory'])}",
            f"- Server coverage_issues: {len(heuristic['coverage_issues'])}",
            f"- audit_shop_coverage: {len(coverage)}",
            "",
        ]
    )

    def section(title: str, rows: list[Any]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not rows:
            lines.append("_none_")
            lines.append("")
            return
        for row in rows:
            lines.append(f"- `{json.dumps(row, ensure_ascii=False)}`")
        lines.append("")

    section("Gaps", heuristic["gaps"])
    section("Wrong product", heuristic["wrong_product"])
    section("Blocked", heuristic["blocked"])
    section("Allergy hits", heuristic["allergy_hits"])
    section("Missing mandatory", heuristic["missing_mandatory"])
    section("Server coverage_issues", heuristic["coverage_issues"])
    section("Server unresolved_ingredients", heuristic["unresolved_ingredients"])
    section("audit_shop_coverage", coverage)
    if cart_audit is not None:
        section("Cart / budget issues", cart_audit.get("cart_issues") or [])
        section("Cart errors", cart_audit.get("cart_errors") or [])

    return findings, "\n".join(lines) + "\n"


def audit_artifacts(out_dir: Path, *, run_index: int, chef_id: str) -> dict[str, Any]:
    profile_blob = json.loads((out_dir / "profile.json").read_text(encoding="utf-8"))
    meal_plan = json.loads((out_dir / "meal_plan.json").read_text(encoding="utf-8"))
    resolved = json.loads((out_dir / "resolved_list.json").read_text(encoding="utf-8"))
    cart_path = out_dir / "cart_result.json"
    cart_result = (
        json.loads(cart_path.read_text(encoding="utf-8")) if cart_path.exists() else None
    )

    answers = profile_blob.get("answers") or {}
    profile_data = profile_blob.get("profile") or answers

    heuristic = run_heuristic_audit(profile_data, meal_plan, resolved)

    coverage: list[dict[str, Any]] = []
    try:
        from shared.models import MealPlan, UserProfile

        # Prefer structured profile from API; fall back to answers mapping.
        if "meals_requested" in profile_data:
            profile_obj = UserProfile.model_validate(profile_data)
        else:
            from agent.conversation import ConversationManager

            profile_obj = ConversationManager().create_profile_from_answers(answers)
        meal_plan_obj = MealPlan.model_validate(meal_plan)
        coverage = run_shop_coverage_audit(profile_obj, meal_plan_obj, resolved)
    except Exception as exc:  # noqa: BLE001 — keep harness usable without package path
        coverage = [{"kind": "audit_error", "detail": str(exc)}]

    cart_audit = None
    meta_path = out_dir / "session_meta.json"
    expect_cart = False
    if meta_path.exists():
        expect_cart = bool(json.loads(meta_path.read_text(encoding="utf-8")).get("cart"))
    if expect_cart or cart_result is not None:
        cart_audit = run_budget_cart_audit(resolved, cart_result)

    findings, report = build_audit_report(
        run_index=run_index,
        chef_id=chef_id,
        heuristic=heuristic,
        coverage=coverage,
        cart_audit=cart_audit,
    )
    write_json(out_dir / "audit_findings.json", findings)
    (out_dir / "audit_report.md").write_text(report, encoding="utf-8")
    return findings


def run_customer(
    *,
    base_url: str,
    run_index: int,
    chef_id: str,
    profile_path: Path,
    out_root: Path,
    cart: bool = False,
) -> Path:
    answers = load_baseline(profile_path)
    answers["chef_id"] = chef_id

    out_dir = out_root / f"run-{run_index:03d}-{chef_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    started = time.perf_counter()
    meta: dict[str, Any] = {
        "run_index": run_index,
        "chef_id": chef_id,
        "base_url": base_url.rstrip("/"),
        "cart": cart,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
        "errors": [],
    }

    timeout = httpx.Timeout(connect=15.0, read=900.0, write=30.0, pool=30.0)
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        # Health
        health = client.get("/api/health")
        if health.status_code >= 400:
            raise RuntimeError(f"API health check failed: {health.status_code} {health.text}")

        start = client.post("/api/session/start")
        start.raise_for_status()
        session_id = start.json()["session_id"]
        meta["session_id"] = session_id
        headers = {"X-Session-Id": session_id, "Content-Type": "application/json"}

        # Attach session header for subsequent calls
        client.headers.update({"X-Session-Id": session_id})

        if cart:
            ww = client.get("/api/session/woolworths/status", headers=headers)
            ww.raise_for_status()
            ww_body = ww.json()
            meta["woolworths"] = ww_body
            if not ww_body.get("connected"):
                write_json(out_dir / "session_meta.json", meta)
                raise RuntimeError(
                    "Woolworths not connected — run `meal-agent login` before --cart runs. "
                    f"Status: {ww_body.get('message')}"
                )

        prof = client.post("/api/profile", json=answers, headers=headers)
        if prof.status_code == 403:
            raise RuntimeError(
                "Premium chef blocked (403). Start API with MEAL_AGENT_DEV_PREMIUM=1 "
                f"or use --chef basic_sam. Detail: {prof.text}"
            )
        prof.raise_for_status()
        prof_body = prof.json()
        write_json(
            out_dir / "profile.json",
            {"answers": answers, "profile": prof_body.get("profile")},
        )

        plan_complete, plan_warns, plan_errs = consume_sse(
            client, "POST", "/api/plan/generate", timeout=600.0
        )
        warnings.extend(plan_warns)
        if plan_errs:
            meta["errors"] = plan_errs
            write_json(out_dir / "session_meta.json", meta)
            raise RuntimeError(f"Plan generate failed: {plan_errs}")
        if not plan_complete or "meal_plan" not in plan_complete:
            raise RuntimeError("Plan generate returned no meal_plan")
        meal_plan = plan_complete["meal_plan"]
        write_json(out_dir / "meal_plan.json", meal_plan)

        approve = client.post("/api/plan/approve", headers=headers)
        approve.raise_for_status()

        shop_complete, shop_warns, shop_errs = consume_sse(
            client, "POST", "/api/shop/resolve?force=true", timeout=600.0
        )
        warnings.extend(shop_warns)
        if shop_errs:
            meta["errors"] = shop_errs
            write_json(out_dir / "session_meta.json", meta)
            raise RuntimeError(f"Shop resolve failed: {shop_errs}")
        if not shop_complete or "resolved_list" not in shop_complete:
            raise RuntimeError("Shop resolve returned no resolved_list")
        resolved = shop_complete["resolved_list"]
        write_json(out_dir / "resolved_list.json", resolved)

        if cart:
            # Start each cart run with an empty trolley
            clear_before = client.post("/api/cart/clear", headers=headers, timeout=60.0)
            if clear_before.status_code >= 400:
                raise RuntimeError(
                    f"Failed to clear trolley before cart add: {clear_before.text}"
                )
            meta["trolley_cleared_before"] = clear_before.json()

            shop_ok = client.post("/api/shop/approve", headers=headers)
            shop_ok.raise_for_status()
            # allow_over_budget so trolley addability is still tested when over budget;
            # budget is assessed separately in the audit.
            cart_res = client.post(
                "/api/cart/add",
                headers=headers,
                json={"allow_over_budget": True, "export_only": False},
                timeout=900.0,
            )
            if cart_res.status_code >= 400:
                detail = cart_res.text
                try:
                    detail = cart_res.json().get("detail", detail)
                except Exception:  # noqa: BLE001
                    pass
                write_json(
                    out_dir / "cart_result.json",
                    {
                        "success_count": 0,
                        "failure_count": 1,
                        "skipped_offline": 0,
                        "added_total": 0,
                        "cart_subtotal": None,
                        "session_lost": False,
                        "errors": [str(detail)],
                        "http_status": cart_res.status_code,
                    },
                )
            else:
                write_json(out_dir / "cart_result.json", cart_res.json())

            # Always empty trolley after the run so items do not accumulate
            clear_after = client.post("/api/cart/clear", headers=headers, timeout=60.0)
            if clear_after.status_code >= 400:
                meta["trolley_clear_after_error"] = clear_after.text
                raise RuntimeError(
                    f"Failed to clear trolley after cart add: {clear_after.text}"
                )
            clear_body = clear_after.json()
            meta["trolley_cleared_after"] = clear_body
            write_json(out_dir / "trolley_clear.json", clear_body)
            if not clear_body.get("cleared", False):
                raise RuntimeError(
                    "Trolley not empty after clear "
                    f"(remaining_sku_count={clear_body.get('remaining_sku_count')})"
                )

    meta["warnings"] = warnings
    meta["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    meta["out_dir"] = str(out_dir)
    write_json(out_dir / "session_meta.json", meta)

    findings = audit_artifacts(out_dir, run_index=run_index, chef_id=chef_id)
    meta["audit_passed"] = findings["passed"]
    meta["issue_count"] = findings["issue_count"]
    meta["checks"] = findings.get("checks")
    write_json(out_dir / "session_meta.json", meta)
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meal-eval customer harness + audit")
    parser.add_argument("--run-index", type=int, default=1, help="1-based run number")
    parser.add_argument(
        "--chef",
        default=None,
        help="Chef id (default: rotate via run-index). One of: " + ", ".join(CHEF_ORDER),
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--cart",
        action="store_true",
        help="Approve shop list and add items to Woolworths trolley",
    )
    parser.add_argument(
        "--shop-only",
        action="store_true",
        help="Stop after shop resolve (default when --cart is omitted)",
    )
    parser.add_argument(
        "--audit-only",
        type=Path,
        default=None,
        help="Only re-audit an existing run directory",
    )
    args = parser.parse_args(argv)
    use_cart = bool(args.cart) and not bool(args.shop_only)

    # Ensure package imports work when run as a script
    for p in (
        ROOT / "packages" / "shared" / "src",
        ROOT / "packages" / "meal_planner" / "src",
        ROOT / "packages" / "agent" / "src",
    ):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)

    if args.audit_only:
        out_dir = args.audit_only
        meta_path = out_dir / "session_meta.json"
        chef_id = args.chef or "unknown"
        run_index = args.run_index
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            chef_id = meta.get("chef_id") or chef_id
            run_index = int(meta.get("run_index") or run_index)
        findings = audit_artifacts(out_dir, run_index=run_index, chef_id=chef_id)
        print(out_dir)
        print("PASS" if findings["passed"] else "FAIL", f"({findings['issue_count']} issues)")
        checks = findings.get("checks") or {}
        if checks:
            print(
                "checks:",
                f"budget={checks.get('within_budget')}",
                f"trolley={checks.get('trolley_ok')}",
                f"products={checks.get('products_ok')}",
            )
        return 0 if findings["passed"] else 2

    chef_id = chef_for_index(args.run_index, args.chef)
    if chef_id not in CHEF_ORDER:
        print(f"Unknown chef_id: {chef_id}", file=sys.stderr)
        return 1

    try:
        out_dir = run_customer(
            base_url=args.base_url,
            run_index=args.run_index,
            chef_id=chef_id,
            profile_path=args.profile,
            out_root=args.out_root,
            cart=use_cart,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    findings = json.loads((out_dir / "audit_findings.json").read_text(encoding="utf-8"))
    print(out_dir)
    print("PASS" if findings["passed"] else "FAIL", f"({findings['issue_count']} issues)")
    print(f"chef={chef_id} cart={use_cart}")
    checks = findings.get("checks") or {}
    if checks:
        print(
            "checks:",
            f"budget={checks.get('within_budget')}",
            f"trolley={checks.get('trolley_ok')}",
            f"products={checks.get('products_ok')}",
        )
    return 0 if findings["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
