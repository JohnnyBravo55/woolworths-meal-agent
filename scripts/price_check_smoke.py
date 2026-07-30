#!/usr/bin/env python3
"""Live smoke for multi-store price check against local meal-agent-api.

Usage:
  python scripts/price_check_smoke.py
  python scripts/price_check_smoke.py --preset chch-central
  python scripts/price_check_smoke.py --store-ids woolworths:christchurch,paknsave:...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_PREFS = ROOT / "profiles" / "web_smoke_prefs.json"

# Imagine living in Christchurch Central — nearby branches with live catalogues.
# FreshChoice City Market is nearby but estimate-only (Myfoodlink not wired).
CHCH_CENTRAL_STORES = [
    "woolworths:christchurch",  # Woolworths Christchurch City
    "new_world:c1aaac72-38c0-4cc0-ad05-f241047d88c5",  # New World Durham Street
    "paknsave:61dd754e-8525-4b9e-9e08-173389eea8a8",  # PAK'nSAVE Moorhouse (Sydenham)
    "new_world:fc91d59f-6ab5-4447-8737-125e09e8e50e",  # New World Ferry Road
]

# Ingredient substring / product junk that usually means a wrong match.
SUSPECT_PRODUCT_HINTS: dict[str, tuple[str, ...]] = {
    "avocado": ("kit", "ranch", "salad", "dip", "guacamole", "oil"),
    "milk": ("coconut", "almond", "oat", "soy", "powder", "chocolate", "condensed"),
    "chicken breast": ("nugget", "tender", "crumb", "schnitzel", "pie", "stock"),
    "beef mince": ("pork", "chicken", "lamb", "sausage", "pie", "patty"),
    "broccoli head": ("bite", "bites", "cheese", "soup", "kit", "salad"),
    "broccoli": ("bite", "bites", "cheese", "soup", "kit", "salad"),
    "rice": ("cracker", "cake", "milk", "wine", "vinegar", "paper"),
    "onion": ("powder", "salt", "soup", "dip"),
    "garlic": ("salt", "powder", "sauce", "bread", "aioli"),
    "egg": ("noodle", "plant", "tofu", "mayonnaise"),
    "butter": ("chicken", "cookie", "peanut"),
    "flour": ("tortilla", "wrap", "mix"),
}


def _sse_complete(client: httpx.Client, method: str, path: str, *, timeout: float) -> dict:
    complete = None
    errors: list[str] = []
    with client.stream(method, path, timeout=timeout) as response:
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.read()[:500]}")
        event = "message"
        data_lines: list[str] = []
        for raw in response.iter_lines():
            if raw is None:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if line == "":
                if data_lines:
                    payload = json.loads("\n".join(data_lines))
                    if event == "complete":
                        complete = payload
                    elif event == "error":
                        errors.append(str(payload.get("message") or payload))
                event = "message"
                data_lines = []
                continue
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            payload = json.loads("\n".join(data_lines))
            if event == "complete":
                complete = payload
            elif event == "error":
                errors.append(str(payload.get("message") or payload))
    if errors and not complete:
        raise RuntimeError("; ".join(errors))
    if not complete:
        raise RuntimeError(f"{method} {path}: no complete event")
    return complete


def _suspect_matches(result: dict) -> list[dict]:
    bad: list[dict] = []
    for basket in result.get("baskets") or []:
        store = (basket.get("store") or {}).get("name") or basket.get("store_id")
        for line in basket.get("lines") or []:
            if line.get("price_source") != "live":
                continue
            ing = str(line.get("ingredient") or "").lower()
            prod = str(line.get("product_name") or "").lower()
            hints = SUSPECT_PRODUCT_HINTS.get(ing) or SUSPECT_PRODUCT_HINTS.get(ing.rstrip("s"))
            if not hints:
                continue
            if any(h in prod for h in hints):
                bad.append(
                    {
                        "store": store,
                        "ingredient": line.get("ingredient"),
                        "product": line.get("product_name"),
                        "price": line.get("unit_price"),
                    }
                )
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description="Live price-check smoke")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--prefs", type=Path, default=DEFAULT_PREFS)
    parser.add_argument("--suburb", default="Christchurch Central")
    parser.add_argument(
        "--preset",
        choices=["", "chch-central"],
        default="chch-central",
        help="Preset store set (default: Christchurch Central multi-chain)",
    )
    parser.add_argument(
        "--store-ids",
        default="",
        help="Comma-separated store ids (overrides preset)",
    )
    args = parser.parse_args()

    prefs = json.loads(args.prefs.read_text(encoding="utf-8"))
    answers = {k: v for k, v in prefs.items() if k != "name"}
    answers.setdefault("chef_id", "basic_sam")

    if args.store_ids.strip():
        pick_ids = [s.strip() for s in args.store_ids.split(",") if s.strip()]
    elif args.preset == "chch-central":
        pick_ids = list(CHCH_CENTRAL_STORES)
    else:
        pick_ids = []

    base = args.base_url.rstrip("/")
    with httpx.Client(base_url=base, timeout=60.0) as client:
        print(f"Health {base}/api/health ...")
        health = client.get("/api/health")
        health.raise_for_status()
        print("  ok", health.json())

        print("Start session ...")
        start = client.post("/api/session/start")
        start.raise_for_status()
        sid = start.json()["session_id"]
        client.headers["X-Session-Id"] = sid
        print(f"  session {sid[:8]}...")

        print(f"Store search q={args.suburb!r} ...")
        stores_res = client.get("/api/stores/search", params={"q": args.suburb, "limit": 20})
        stores_res.raise_for_status()
        stores = stores_res.json().get("stores") or []
        print(f"  found {len(stores)} store(s) near suburb")
        for s in stores[:10]:
            print(f"    - {s.get('chain')}: {s.get('name')} ({s.get('id')})")

        if not pick_ids:
            by_chain: dict[str, dict] = {}
            for s in stores:
                by_chain.setdefault(str(s.get("chain")), s)
            for chain in ("woolworths", "paknsave", "new_world", "freshchoice"):
                if chain in by_chain and len(pick_ids) < 4:
                    pick_ids.append(by_chain[chain]["id"])
            if not pick_ids and stores:
                pick_ids = [stores[0]["id"]]

        print(f"Using {len(pick_ids)} store(s):")
        for sid_pick in pick_ids:
            print(f"    - {sid_pick}")

        print("Save profile ...")
        client.post("/api/profile", json=answers).raise_for_status()

        print("Generate meal plan (may take a minute) ...")
        plan_done = _sse_complete(client, "POST", "/api/plan/generate", timeout=300.0)
        meals = (plan_done.get("meal_plan") or {}).get("meals") or []
        print(f"  plan meals={len(meals)}")

        print("Approve plan ...")
        client.post("/api/plan/approve").raise_for_status()

        print("Resolve shop list (may take a minute) ...")
        shop_done = _sse_complete(client, "POST", "/api/shop/resolve", timeout=300.0)
        resolved = shop_done.get("resolved_list") or {}
        items = resolved.get("items") or []
        print(f"  shop items={len(items)} total=${resolved.get('total')}")
        if not items:
            print("FAIL: empty shop list", file=sys.stderr)
            return 1

        print("POST /api/price-check ...")
        pc = client.post(
            "/api/price-check",
            json={"store_ids": pick_ids, "include_split": True},
            timeout=240.0,
        )
        if pc.status_code >= 400:
            print(f"FAIL: price-check {pc.status_code} {pc.text[:800]}", file=sys.stderr)
            return 1
        result = pc.json()
        baskets = result.get("baskets") or []
        print(f"  baskets={len(baskets)}")
        live_total = 0
        est_total = 0
        for b in baskets:
            live = int(b.get("live_count") or 0)
            est = int(b.get("estimate_count") or 0)
            live_total += live
            est_total += est
            store_label = (
                (b.get("store") or {}).get("name")
                or b.get("store_name")
                or b.get("store_id")
                or "store"
            )
            chain = (b.get("store") or {}).get("chain") or ""
            print(
                f"    [{chain}] {store_label}: total=${b.get('total')} "
                f"live={live} estimate={est}"
            )
            for line in (b.get("lines") or [])[:4]:
                src = line.get("price_source")
                print(
                    f"      [{src}] {line.get('ingredient')} -> "
                    f"{line.get('product_name')} ${line.get('unit_price')}"
                )
        split = result.get("split")
        if split:
            print(
                f"  split total=${split.get('total')} "
                f"savings=${split.get('savings_vs_cheapest_single_store')}"
            )

        suspects = _suspect_matches(result)
        out = ROOT / "output" / "price-check-smoke.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "store_ids": pick_ids,
            "suburb": args.suburb,
            "suspects": suspects,
            "result": result,
        }
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        if live_total < 1:
            print("FAIL: no live prices matched", file=sys.stderr)
            return 1
        if suspects:
            print(f"FAIL: {len(suspects)} suspect wrong-product match(es):", file=sys.stderr)
            for s in suspects[:20]:
                print(f"  - {s['store']}: {s['ingredient']} -> {s['product']}", file=sys.stderr)
            print(f"Wrote {out}")
            return 2

        print(f"PASS: live prices ok (live={live_total}, estimate={est_total}) -> {out}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
