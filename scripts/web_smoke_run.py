#!/usr/bin/env python3
"""Hosted web smoke: preferences → meal plan → shop list (no Woolworths login).

Usage:
  python scripts/web_smoke_run.py
  python scripts/web_smoke_run.py --headed
  python scripts/web_smoke_run.py --base-url https://johnnybravo55.github.io/woolworths-meal-agent/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

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
    # Last resort: substring match on first text
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
    # Prefs are optional enhancements; continue with defaults if missing.


def _assert_no_woolworths_connect(page) -> None:
    url = page.url.lower()
    if WW_FORBIDDEN_URL in url:
        raise SmokeFail(f"Navigated to Woolworths connect page: {page.url}")
    if "/cart" in url and "shop" not in url:
        # Expo routes: .../cart — fail if we landed on cart accidentally
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
            # Ensure generate spinner is gone
            generating = page.get_by_text("Generating…", exact=True)
            if generating.count() == 0 or not generating.first.is_visible():
                return
        time.sleep(1.0)
    raise SmokeFail("Timed out waiting for meal plan / Approve plan")


def run_smoke(
    *,
    base_url: str,
    access_code: str,
    prefs_path: Path,
    headed: bool,
    out_dir: Path,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "playwright is not installed. Run: pip install -e \".[e2e]\" && playwright install chromium"
        ) from e

    prefs = _load_prefs(prefs_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    url = base_url.rstrip("/") + "/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        try:
            print(f"Opening {url}")
            page.goto(url, wait_until="domcontentloaded")
            _assert_no_woolworths_connect(page)

            # Access gate (may already be unlocked in sessionStorage from prior runs — fresh context so expect gate)
            gate_input = page.get_by_test_id("access-code-input")
            if gate_input.count() == 0:
                gate_input = page.get_by_placeholder("Access code")
            if gate_input.count() > 0 and gate_input.first.is_visible():
                print("Unlocking access gate…")
                gate_input.first.fill(access_code)
                _click_by_testid_or_text(page, "access-code-continue", "Continue", "Checking…")
                # Wait for preferences
                page.get_by_text("Preferences", exact=True).first.wait_for(
                    state="visible", timeout=NAV_TIMEOUT_MS
                )
            else:
                print("Access gate not shown (already unlocked or gate disabled)")

            _assert_no_woolworths_connect(page)
            page.get_by_text("Preferences", exact=True).first.wait_for(
                state="visible", timeout=NAV_TIMEOUT_MS
            )

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

            # Final guard: still not on connect/cart
            url_now = page.url.lower()
            if WW_FORBIDDEN_URL in url_now:
                raise SmokeFail(f"Ended on connect page: {page.url}")
            if url_now.rstrip("/").endswith("/cart"):
                raise SmokeFail(f"Ended on cart page: {page.url}")

            print("PASS: shop list reached without Woolworths login.")
            (out_dir / "result.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "url": page.url,
                        "prefs": prefs,
                        "base_url": base_url,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as e:
            shot = out_dir / "failure.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                print(f"Screenshot saved to {shot}")
            except Exception as shot_err:
                print(f"Could not save screenshot: {shot_err}")
            (out_dir / "result.json").write_text(
                json.dumps(
                    {
                        "ok": False,
                        "error": str(e),
                        "url": page.url if page else None,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            raise
        finally:
            context.close()
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hosted web smoke through shop list")
    parser.add_argument("--base-url", default=os.environ.get("WEB_SMOKE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--access-code",
        default=os.environ.get("MEAL_AGENT_ACCESS_CODE", "usertest1"),
    )
    parser.add_argument("--prefs", type=Path, default=DEFAULT_PREFS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    args = parser.parse_args(argv)

    try:
        run_smoke(
            base_url=args.base_url,
            access_code=args.access_code,
            prefs_path=args.prefs,
            headed=args.headed,
            out_dir=args.out_dir,
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
