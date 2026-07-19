#!/usr/bin/env python3
"""Hosted web smoke: preferences → meal plan → shop list (+ plan/shop alignment audit).

Usage:
  python scripts/web_smoke_run.py
  python scripts/web_smoke_run.py --run-index 1
  python scripts/web_smoke_run.py --headed
  python scripts/web_smoke_run.py --base-url https://johnnybravo55.github.io/woolworths-meal-agent/
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://johnnybravo55.github.io/woolworths-meal-agent/"
DEFAULT_PREFS = ROOT / "profiles" / "web_smoke_prefs.json"
DEFAULT_OUT = ROOT / "output" / "web-smoke"

# Render cold start + LLM plan + product resolve
NAV_TIMEOUT_MS = 90_000
ACTION_TIMEOUT_MS = 30_000
PLAN_TIMEOUT_MS = 300_000
SHOP_TIMEOUT_MS = 300_000

WW_FORBIDDEN_URL = "connect-woolworths"
# Exact connect-flow copy only — avoid matching status hints like "Sign in at Add to cart".
WW_FORBIDDEN_TEXT = (
    "Connect to Woolworths",
    "Connect Woolworths",
    "Sign in to Woolworths",
    "Sign in first — your shop list",
    "Open Woolworths sign-in",
    "I've clicked Connect in the extension",
)


class SmokeFail(Exception):
    """Soft assertion failure with a clear message."""


def _load_prefs(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_meal_eval():
    path = ROOT / "scripts" / "meal_eval_run.py"
    spec = importlib.util.spec_from_file_location("meal_eval_run", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _click_by_testid_or_text(page, test_id: str, *texts: str, timeout: int = ACTION_TIMEOUT_MS) -> None:
    by_id = page.get_by_test_id(test_id)
    if by_id.count() > 0:
        by_id.first.click(timeout=timeout)
        return
    for text in texts:
        loc = page.get_by_text(text, exact=True)
        if loc.count() > 0:
            loc.first.click(timeout=timeout)
            return
    if texts:
        page.get_by_text(texts[0]).first.click(timeout=timeout)
        return
    raise SmokeFail(f"Could not find control testid={test_id!r} texts={texts!r}")


def _fill_by_testid_or_placeholder(
    page,
    test_id: str,
    value: str,
    *,
    placeholder: str | None = None,
    label: str | None = None,
) -> None:
    by_id = page.get_by_test_id(test_id)
    if by_id.count() > 0:
        by_id.first.fill(value)
        return
    if placeholder:
        by_ph = page.get_by_placeholder(placeholder)
        if by_ph.count() > 0:
            by_ph.first.fill(value)
            return
    if label:
        by_label = page.get_by_label(label)
        if by_label.count() > 0:
            by_label.first.fill(value)
            return


def _assert_no_woolworths_connect(page) -> None:
    url = page.url.lower()
    if WW_FORBIDDEN_URL in url:
        raise SmokeFail(f"Navigated to Woolworths connect page: {page.url}")
    if url.rstrip("/").endswith("/cart"):
        raise SmokeFail(f"Navigated to cart (out of scope): {page.url}")
    for text in WW_FORBIDDEN_TEXT:
        loc = page.get_by_text(text, exact=True)
        if loc.count() == 0:
            loc = page.get_by_text(text, exact=False)
        if loc.count() > 0 and loc.first.is_visible():
            raise SmokeFail(
                f"Woolworths connect/sign-in UI visible: {text!r} "
                "(hosted Pages may be behind local web-skip fixes — redeploy apps/mobile)"
            )


def _wait_shop_summary(page) -> None:
    deadline = time.monotonic() + SHOP_TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        _assert_no_woolworths_connect(page)
        by_id = page.get_by_test_id("shop-summary")
        if by_id.count() > 0 and by_id.first.is_visible():
            return
        will_add = page.get_by_text("Will add:", exact=False)
        if will_add.count() > 0 and will_add.first.is_visible():
            return
        time.sleep(1.0)
    raise SmokeFail("Timed out waiting for shop list summary")


def _wait_plan_ready(page) -> None:
    deadline = time.monotonic() + PLAN_TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        _assert_no_woolworths_connect(page)
        approve = page.get_by_test_id("plan-approve")
        if approve.count() == 0:
            approve = page.get_by_text("Approve plan →", exact=True)
        if approve.count() > 0 and approve.first.is_visible():
            generating = page.get_by_text("Generating…", exact=True)
            if generating.count() == 0 or not generating.first.is_visible():
                return
        time.sleep(1.0)
    raise SmokeFail("Timed out waiting for meal plan / Approve plan")


def _is_api_url(url: str) -> bool:
    try:
        path = urlparse(url).path or ""
    except Exception:  # noqa: BLE001
        return False
    return "/api/" in path


def _fetch_plan_and_shop(
    *,
    api_base: str,
    session_id: str,
    access_code: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import httpx

    headers = {
        "X-Session-Id": session_id,
        "Content-Type": "application/json",
    }
    if access_code:
        headers["X-Access-Code"] = access_code

    base = api_base.rstrip("/")
    with httpx.Client(timeout=60.0, headers=headers) as client:
        plan_res = client.get(f"{base}/api/plan")
        plan_res.raise_for_status()
        plan_body = plan_res.json()
        meal_plan = plan_body.get("meal_plan") or plan_body
        if not isinstance(meal_plan, dict) or not meal_plan.get("meals"):
            raise SmokeFail(f"API /api/plan missing meals: {plan_body!r}")

        shop_res = client.get(f"{base}/api/shop/list")
        shop_res.raise_for_status()
        shop_body = shop_res.json()
        resolved = shop_body.get("resolved_list") or shop_body
        if not isinstance(resolved, dict) or "items" not in resolved:
            raise SmokeFail(f"API /api/shop/list missing resolved_list: {shop_body!r}")
        return meal_plan, resolved


def _audit_alignment(
    *,
    prefs: dict[str, Any],
    meal_plan: dict[str, Any],
    resolved: dict[str, Any],
    out_dir: Path,
    run_index: int,
) -> dict[str, Any]:
    meal_eval = _load_meal_eval()
    heuristic = meal_eval.run_heuristic_audit(prefs, meal_plan, resolved)

    coverage: list[dict[str, Any]] = []
    try:
        from agent.conversation import ConversationManager
        from shared.models import MealPlan as MealPlanModel

        answers = {k: v for k, v in prefs.items() if k != "name"}
        profile_obj = ConversationManager().create_profile_from_answers(answers)
        meal_plan_obj = MealPlanModel.model_validate(meal_plan)
        coverage = meal_eval.run_shop_coverage_audit(profile_obj, meal_plan_obj, resolved)
    except Exception as exc:  # noqa: BLE001
        # Coverage audit is best-effort; heuristic still runs.
        coverage = [{"kind": "audit_error", "detail": str(exc)}]

    findings, report = meal_eval.build_audit_report(
        run_index=run_index,
        chef_id=str(prefs.get("chef_id") or "basic_sam"),
        heuristic=heuristic,
        coverage=coverage,
        cart_audit=None,
    )
    # Web smoke does not care about trolley; products_ok is the alignment gate.
    products_ok = bool(findings.get("checks", {}).get("products_ok"))
    findings["passed"] = products_ok
    findings["checks"]["within_budget"] = None
    findings["checks"]["trolley_ok"] = None

    (out_dir / "meal_plan.json").write_text(
        json.dumps(meal_plan, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "resolved_list.json").write_text(
        json.dumps(resolved, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "audit_findings.json").write_text(
        json.dumps(findings, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "audit_report.md").write_text(report, encoding="utf-8")
    return findings


def run_smoke(
    *,
    base_url: str,
    access_code: str,
    prefs_path: Path,
    headed: bool,
    out_dir: Path,
    run_index: int,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            'playwright is not installed. Run: pip install -e ".[e2e]" && playwright install chromium'
        ) from e

    prefs = _load_prefs(prefs_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    url = base_url.rstrip("/") + "/"

    captured_api_base: dict[str, str] = {"url": ""}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        def on_request(request) -> None:
            if _is_api_url(request.url) and not captured_api_base["url"]:
                parsed = urlparse(request.url)
                captured_api_base["url"] = f"{parsed.scheme}://{parsed.netloc}"

        page.on("request", on_request)

        try:
            print(f"Opening {url}")
            page.goto(url, wait_until="domcontentloaded")
            _assert_no_woolworths_connect(page)

            gate_input = page.get_by_test_id("access-code-input")
            if gate_input.count() == 0:
                gate_input = page.get_by_placeholder("Access code")
            if gate_input.count() > 0 and gate_input.first.is_visible():
                print("Unlocking access gate…")
                gate_input.first.fill(access_code)
                _click_by_testid_or_text(page, "access-code-continue", "Continue", "Checking…")
            else:
                print("Access gate not shown (already unlocked or gate disabled)")

            prefs = page.get_by_text("Preferences", exact=True)
            nda_name = page.get_by_test_id("nda-full-name")
            deadline = time.time() + (NAV_TIMEOUT_MS / 1000.0)
            saw_nda = False
            while time.time() < deadline:
                if nda_name.count() > 0 and nda_name.first.is_visible():
                    saw_nda = True
                    break
                if prefs.count() > 0 and prefs.first.is_visible():
                    break
                page.wait_for_timeout(200)
            if saw_nda:
                print("Accepting NDA…")
                nda_name.first.fill("Web Smoke Tester")
                _click_by_testid_or_text(
                    page,
                    "nda-agree",
                    "I Agree to the Confidential Beta Testing Agreement",
                )
                _click_by_testid_or_text(
                    page, "nda-accept", "Accept & Begin Beta Test", "Submitting…"
                )

            _assert_no_woolworths_connect(page)
            prefs.first.wait_for(state="visible", timeout=NAV_TIMEOUT_MS)

            print("Filling fabricated preferences…")
            budget = prefs.get("budget_nzd")
            if budget is not None and float(budget) > 0:
                _fill_by_testid_or_placeholder(
                    page,
                    "discovery-budget",
                    str(int(budget) if float(budget) == int(budget) else budget),
                    placeholder="Leave blank for no hard budget",
                    label="Weekly budget NZD",
                )
            likes = prefs.get("likes") or ""
            if likes:
                _fill_by_testid_or_placeholder(
                    page,
                    "discovery-likes",
                    likes,
                    placeholder="chicken, pasta, japanese",
                    label="Likes",
                )
            dislikes = prefs.get("dislikes") or ""
            if dislikes:
                _fill_by_testid_or_placeholder(
                    page,
                    "discovery-dislikes",
                    dislikes,
                    placeholder="lamb, coriander",
                    label="Dislikes",
                )
            mandatory = prefs.get("mandatory_items") or ""
            if mandatory:
                _fill_by_testid_or_placeholder(
                    page,
                    "discovery-mandatory",
                    mandatory,
                    placeholder="milk, bread",
                    label="Mandatory items",
                )
            pantry = prefs.get("pantry_items") or ""
            if pantry:
                _fill_by_testid_or_placeholder(
                    page,
                    "discovery-pantry",
                    pantry,
                    placeholder="olive oil, rice, soy sauce",
                    label="Already in pantry",
                )

            print("Continue to chef…")
            _click_by_testid_or_text(page, "discovery-continue", "Continue to chef →")
            page.get_by_text("Generate meal plan →", exact=False).first.wait_for(
                state="visible", timeout=NAV_TIMEOUT_MS
            )
            _assert_no_woolworths_connect(page)

            print("Generating meal plan (may take several minutes)…")
            _click_by_testid_or_text(
                page,
                "chef-generate",
                "Generate meal plan →",
                "Continue to meal plan →",
                timeout=ACTION_TIMEOUT_MS,
            )
            _wait_plan_ready(page)
            _assert_no_woolworths_connect(page)

            print("Approving plan…")
            _click_by_testid_or_text(page, "plan-approve", "Approve plan →")
            page.get_by_text("Build shop list", exact=False).first.wait_for(
                state="visible", timeout=NAV_TIMEOUT_MS
            )
            _assert_no_woolworths_connect(page)

            print("Building shop list (may take several minutes)…")
            _click_by_testid_or_text(
                page,
                "recipes-build-shop",
                "Build shop list →",
                "Re-build shop list",
            )
            _wait_shop_summary(page)
            _assert_no_woolworths_connect(page)

            url_now = page.url.lower()
            if WW_FORBIDDEN_URL in url_now:
                raise SmokeFail(f"Ended on connect page: {page.url}")
            if url_now.rstrip("/").endswith("/cart"):
                raise SmokeFail(f"Ended on cart page: {page.url}")

            print("PASS (UI): shop list reached without Woolworths login.")

            session_id = page.evaluate("() => localStorage.getItem('meal_agent_session')")
            if not session_id:
                raise SmokeFail("No meal_agent_session in localStorage — cannot audit alignment")

            api_base = captured_api_base["url"]
            if not api_base:
                # Fallback: read baked-in Expo extra if present on window
                api_base = page.evaluate(
                    """() => {
                      try {
                        return (window.__EXPO_PUBLIC_API_URL
                          || (window.expoConfig && window.expoConfig.extra && window.expoConfig.extra.apiUrl)
                          || '');
                      } catch (e) { return ''; }
                    }"""
                )
            if not api_base:
                raise SmokeFail("Could not determine API base URL for alignment audit")

            print(f"Auditing plan vs shop via {api_base} (session {session_id[:8]}…)…")
            meal_plan, resolved = _fetch_plan_and_shop(
                api_base=api_base,
                session_id=session_id,
                access_code=access_code,
            )
            findings = _audit_alignment(
                prefs=prefs,
                meal_plan=meal_plan,
                resolved=resolved,
                out_dir=out_dir,
                run_index=run_index,
            )
            heuristic = findings.get("heuristic") or {}
            print(
                f"Alignment: covered={heuristic.get('covered')} "
                f"gaps={len(heuristic.get('gaps') or [])} "
                f"wrong={len(heuristic.get('wrong_product') or [])} "
                f"mandatory_missing={heuristic.get('missing_mandatory')} "
                f"coverage={len(findings.get('shop_coverage') or [])}"
            )

            result = {
                "ok": bool(findings.get("passed")),
                "url": page.url,
                "prefs": prefs,
                "base_url": base_url,
                "api_base": api_base,
                "session_id": session_id,
                "audit": {
                    "passed": findings.get("passed"),
                    "issue_count": findings.get("issue_count"),
                    "checks": findings.get("checks"),
                    "gaps": heuristic.get("gaps"),
                    "wrong_product": heuristic.get("wrong_product"),
                    "missing_mandatory": heuristic.get("missing_mandatory"),
                    "coverage_issues": heuristic.get("coverage_issues"),
                    "shop_coverage": findings.get("shop_coverage"),
                },
            }
            (out_dir / "result.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )

            if not findings.get("passed"):
                raise SmokeFail(
                    f"Plan/shop misaligned ({findings.get('issue_count')} issue(s)) — "
                    f"see {out_dir / 'audit_report.md'}"
                )

            print("PASS: shop list reached and plan/shop align.")
        except Exception as e:
            shot = out_dir / "failure.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                print(f"Screenshot saved to {shot}")
            except Exception as shot_err:
                print(f"Could not save screenshot: {shot_err}")
            existing = {}
            if (out_dir / "result.json").exists():
                try:
                    existing = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    existing = {}
            existing.update(
                {
                    "ok": False,
                    "error": str(e),
                    "url": page.url if page else None,
                }
            )
            (out_dir / "result.json").write_text(
                json.dumps(existing, indent=2) + "\n", encoding="utf-8"
            )
            raise
        finally:
            context.close()
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hosted web smoke through shop list + plan/shop alignment"
    )
    parser.add_argument("--base-url", default=os.environ.get("WEB_SMOKE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--access-code",
        default=os.environ.get("MEAL_AGENT_ACCESS_CODE", "usertest1"),
    )
    parser.add_argument("--prefs", type=Path, default=DEFAULT_PREFS)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--run-index", type=int, default=1)
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    args = parser.parse_args(argv)

    out_dir = args.out_dir or (DEFAULT_OUT / f"run-{args.run_index:03d}")

    try:
        run_smoke(
            base_url=args.base_url,
            access_code=args.access_code,
            prefs_path=args.prefs,
            headed=args.headed,
            out_dir=out_dir,
            run_index=args.run_index,
        )
        return 0
    except SmokeFail as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
