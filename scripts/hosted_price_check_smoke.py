#!/usr/bin/env python3
"""Hosted E2E: gate → prefs → chef → plan → shop → multi-store price check.

Targets the live Pages site + Render API (same flow users hit).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "https://meals.pyxstudio.nz/"
DEFAULT_API = "https://mealagent.pyxstudio.nz"
DEFAULT_PREFS = ROOT / "profiles" / "web_smoke_prefs.json"
OUT = ROOT / "output" / "hosted-price-check-smoke"

CHCH_STORES = [
    "woolworths:christchurch",
    "new_world:c1aaac72-38c0-4cc0-ad05-f241047d88c5",
    "paknsave:61dd754e-8525-4b9e-9e08-173389eea8a8",
    "freshchoice:citymarket",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--api-url", default=os.environ.get("MEAL_AGENT_API_URL", DEFAULT_API))
    parser.add_argument("--access-code", default=os.environ.get("MEAL_AGENT_ACCESS_CODE", "usertest1"))
    parser.add_argument("--prefs", type=Path, default=DEFAULT_PREFS)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install playwright: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    prefs = json.loads(args.prefs.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(60_000)

        print(f"Open {args.base_url}")
        page.goto(args.base_url, wait_until="domcontentloaded", timeout=90_000)

        # Access gate
        gate = page.get_by_test_id("access-code-input")
        if gate.count() == 0:
            gate = page.get_by_placeholder("Access code")
        if gate.count() > 0:
            print("Enter access code…")
            gate.first.fill(args.access_code)
            cont = page.get_by_test_id("access-code-continue")
            if cont.count() == 0:
                cont = page.get_by_role("button", name="Continue")
            cont.first.click()
            page.wait_for_timeout(1500)

        # Preferences — fill suburb for Chch
        print("Preferences…")
        suburb = page.get_by_placeholder("Ferrymead")
        if suburb.count() > 0:
            suburb.first.fill("Christchurch Central")
        # mandatory / likes if present
        for placeholder, value in (
            ("milk, gluten free bread", "milk"),
            ("e.g. gluten, nuts", ""),
        ):
            loc = page.get_by_placeholder(placeholder)
            if loc.count() > 0 and value:
                loc.first.fill(value)

        choose = page.get_by_test_id("prefs-continue")
        if choose.count() == 0:
            choose = page.get_by_role("button", name="Choose your chef")
        choose.first.click()

        # Chef
        print("Chef…")
        page.wait_for_timeout(1000)
        sam = page.get_by_text("Basic Sam", exact=False)
        if sam.count() > 0:
            sam.first.click()
        cont = page.get_by_role("button", name="Continue")
        if cont.count() == 0:
            cont = page.get_by_test_id("chef-continue")
        if cont.count() > 0:
            cont.first.click()

        # Generate plan
        print("Generate plan (may take a minute)…")
        gen = page.get_by_role("button", name="Generate")
        if gen.count() == 0:
            gen = page.get_by_test_id("plan-generate")
        if gen.count() > 0:
            gen.first.click()
        page.wait_for_selector("text=/dinner|Meal|Approve/i", timeout=300_000)
        approve = page.get_by_role("button", name="Approve")
        if approve.count() == 0:
            approve = page.get_by_test_id("plan-approve")
        approve.first.click()

        # Recipes → shop
        print("Recipes → shop…")
        page.wait_for_timeout(2000)
        to_shop = page.get_by_role("button", name="Build shop list")
        if to_shop.count() == 0:
            to_shop = page.get_by_role("button", name="Shop list")
        if to_shop.count() == 0:
            to_shop = page.get_by_test_id("recipes-continue")
        if to_shop.count() > 0:
            to_shop.first.click()

        page.wait_for_selector("text=/Shop list|Compare store prices|Run price check/i", timeout=300_000)
        print("On shop list")

        # Open price check
        run_pc = page.get_by_role("button", name="Run price check")
        if run_pc.count() == 0:
            page.screenshot(path=str(OUT / "no-price-check.png"), full_page=True)
            print("FAIL: Run price check button not found", file=sys.stderr)
            browser.close()
            return 1
        run_pc.first.click()
        page.wait_for_timeout(1500)

        search = page.get_by_placeholder("Search suburb or store")
        if search.count() > 0:
            search.first.fill("Christchurch")
            page.wait_for_timeout(2500)

        # Select up to 4 stores by visible names
        wanted = [
            "Woolworths Christchurch",
            "PAK'nSAVE Moorhouse",
            "New World Durham",
            "FreshChoice Christchurch City",
            "FreshChoice City",
        ]
        selected = 0
        for name in wanted:
            row = page.get_by_text(name, exact=False)
            if row.count() > 0 and selected < 4:
                row.first.click()
                selected += 1
                page.wait_for_timeout(400)
        print(f"Selected ~{selected} store row(s)")

        compare = page.get_by_role("button", name="Compare")
        if compare.count() == 0:
            compare = page.get_by_text("Compare", exact=False)
        if compare.count() == 0:
            page.screenshot(path=str(OUT / "no-compare.png"), full_page=True)
            print("FAIL: Compare button not found", file=sys.stderr)
            browser.close()
            return 1
        compare.first.click()
        print("Running price check…")
        # Wait for results: live counts or basket totals
        try:
            page.wait_for_selector("text=/live|estimate|split|total|NZ\\$/i", timeout=240_000)
        except Exception:
            page.screenshot(path=str(OUT / "price-check-timeout.png"), full_page=True)
            print("FAIL: price check results timeout", file=sys.stderr)
            browser.close()
            return 1

        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "price-check-result.png"), full_page=True)
        body = page.inner_text("body")
        (OUT / "page-text.txt").write_text(body, encoding="utf-8")

        # Also call API directly with cookies/session if we can extract session
        # Prefer: use access code against API for a clean verification parallel path
        print("Verifying via API…")
        import httpx

        api = args.api_url.rstrip("/")
        headers = {"X-Access-Code": args.access_code, "Content-Type": "application/json"}
        with httpx.Client(base_url=api, headers=headers, timeout=120.0, follow_redirects=True) as client:
            start = client.post("/api/session/start")
            start.raise_for_status()
            sid = start.json()["session_id"]
            client.headers["X-Session-Id"] = sid
            answers = {k: v for k, v in prefs.items() if k != "name"}
            answers["chef_id"] = "basic_sam"
            answers["store_name"] = "Christchurch Central"
            client.post("/api/profile", json=answers).raise_for_status()

            # SSE helpers
            def sse(method: str, path: str, timeout: float = 300.0, json_body: dict | None = None) -> dict:
                complete = None
                with client.stream(method, path, json=json_body, timeout=timeout) as resp:
                    resp.raise_for_status()
                    event = "message"
                    data_lines: list[str] = []
                    for raw in resp.iter_lines():
                        line = raw.decode() if isinstance(raw, bytes) else raw
                        if line == "":
                            if data_lines:
                                payload = json.loads("\n".join(data_lines))
                                if event == "complete":
                                    complete = payload
                                elif event == "error":
                                    raise RuntimeError(str(payload))
                            event = "message"
                            data_lines = []
                            continue
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line[5:].lstrip())
                if not complete:
                    raise RuntimeError(f"no complete for {path}")
                return complete

            sse("POST", "/api/plan/generate")
            client.post("/api/plan/approve").raise_for_status()
            shop = sse("POST", "/api/shop/resolve")
            items = (shop.get("resolved_list") or {}).get("items") or []
            print(f"API shop items={len(items)}")
            stores = client.get(
                "/api/stores/search", params={"q": "Christchurch Central", "limit": 20}
            )
            stores.raise_for_status()
            store_list = stores.json().get("stores") or []
            print(f"API stores found={len(store_list)}")
            fc = [s for s in store_list if s.get("chain") == "freshchoice"]
            print(f"  freshchoice hits={len(fc)}")

            result = sse(
                "POST",
                "/api/price-check",
                timeout=420.0,
                json_body={"store_ids": CHCH_STORES, "include_split": True},
            )
            (OUT / "api-price-check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            issues = []
            for b in result.get("baskets") or []:
                store = b.get("store") or {}
                live = int(b.get("live_count") or 0)
                est = int(b.get("estimate_count") or 0)
                n = live + est
                pct = round(100 * live / n, 1) if n else 0
                note = store.get("pricing_note") or ""
                warn = str(b.get("warning") or "")
                print(
                    f"  [{store.get('chain')}] {store.get('name')}: "
                    f"live={live}/{n} ({pct}%) est={est} note={note!r} warning={warn!r}"
                )
                if store.get("chain") == "freshchoice" and "not wired" in note.lower():
                    issues.append("FreshChoice still estimate-only on Render (old deploy?)")
                if live < 1 and store.get("chain") != "woolworths":
                    issues.append(f"{store.get('name')}: zero live matches")
                if store.get("chain") == "freshchoice" and pct < 50:
                    issues.append(f"FreshChoice live match rate too low: {pct}%")

            if issues:
                print("FAIL issues:", file=sys.stderr)
                for i in issues:
                    print(f"  - {i}", file=sys.stderr)
                browser.close()
                return 2

        print(f"PASS — artifacts in {OUT}")
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
