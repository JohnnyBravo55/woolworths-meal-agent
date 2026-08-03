#!/usr/bin/env python3
"""Live smoke for multi-store price check against local meal-agent-api.

Full flow: session → prefs → plan → approve → shop → price-check.

Usage:
  python scripts/price_check_smoke.py
  python scripts/price_check_smoke.py --preset chch-central --runs 5
  python scripts/price_check_smoke.py --store-ids woolworths:christchurch,paknsave:...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "packages" / "price_check" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "price_check" / "src"))

from price_check.matching import score_product_name  # noqa: E402

DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_PREFS = ROOT / "profiles" / "web_smoke_prefs.json"

CHEF_ORDER = [
    "basic_sam",
    "premium_elena",
    "premium_kenji",
    "premium_moana",
    "premium_alex",
    "premium_amara",
]

# Imagine living in Christchurch Central — nearby branches with live catalogues.
# WW is priced on the shop list (online catalogue), not in multi-store compare.
CHCH_CENTRAL_STORES = [
    "new_world:c1aaac72-38c0-4cc0-ad05-f241047d88c5",  # New World Durham Street
    "paknsave:61dd754e-8525-4b9e-9e08-173389eea8a8",  # PAK'nSAVE Moorhouse (Sydenham)
    "freshchoice:citymarket",  # FreshChoice Christchurch City Market
    "paknsave:8cd700ae-d96f-4761-bd7a-805d6b93536d",  # PAK'nSAVE Papanui
]

# Ingredient substring / product junk that usually means a wrong match.
SUSPECT_PRODUCT_HINTS: dict[str, tuple[str, ...]] = {
    "avocado": ("kit", "ranch", "salad", "dip", "guacamole", "oil"),
    "milk": ("coconut", "almond", "oat", "soy", "powder", "chocolate", "condensed"),
    "chicken breast": ("nugget", "tender", "crumb", "schnitzel", "pie", "stock"),
    "chicken thighs": ("nugget", "tenderbasted", "crumb", "schnitzel", "pie", "stock"),
    "chicken thigh": ("nugget", "tenderbasted", "crumb", "schnitzel", "pie", "stock"),
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


def _sse_complete(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    timeout: float,
    json_body: dict | None = None,
) -> dict:
    complete = None
    errors: list[str] = []
    with client.stream(method, path, json=json_body, timeout=timeout) as response:
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
            prod = str(line.get("product_name") or "")
            prod_l = prod.lower()
            reasons: list[str] = []
            if score_product_name(ing, prod) <= 0:
                reasons.append("matcher_rejects")
            hints = (
                SUSPECT_PRODUCT_HINTS.get(ing)
                or SUSPECT_PRODUCT_HINTS.get(ing.rstrip("s"))
                or ()
            )
            if hints and any(h in prod_l for h in hints):
                reasons.append("hint")
            if reasons:
                bad.append(
                    {
                        "store": store,
                        "ingredient": line.get("ingredient"),
                        "product": line.get("product_name"),
                        "price": line.get("unit_price"),
                        "reasons": reasons,
                    }
                )
    return bad


def _basket_stats(result: dict) -> list[dict]:
    rows: list[dict] = []
    for b in result.get("baskets") or []:
        store = b.get("store") or {}
        live = int(b.get("live_count") or 0)
        est = int(b.get("estimate_count") or 0)
        n = live + est
        rows.append(
            {
                "chain": store.get("chain") or "",
                "name": store.get("name") or b.get("store_id") or "store",
                "live": live,
                "estimate": est,
                "items": n,
                "live_pct": round(100.0 * live / n, 1) if n else 0.0,
                "estimate_pct": round(100.0 * est / n, 1) if n else 0.0,
                "total": b.get("total"),
            }
        )
    return rows


def run_once(
    *,
    base_url: str,
    prefs_path: Path,
    suburb: str,
    pick_ids: list[str],
    chef_id: str,
    run_index: int,
    out_dir: Path,
) -> dict:
    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
    answers = {k: v for k, v in prefs.items() if k != "name"}
    answers["chef_id"] = chef_id

    base = base_url.rstrip("/")
    with httpx.Client(base_url=base, timeout=60.0) as client:
        print(f"\n===== RUN {run_index:03d} chef={chef_id} =====")
        health = client.get("/api/health")
        health.raise_for_status()

        start = client.post("/api/session/start")
        start.raise_for_status()
        sid = start.json()["session_id"]
        client.headers["X-Session-Id"] = sid
        print(f"  session {sid[:8]}...")

        stores_res = client.get("/api/stores/search", params={"q": suburb, "limit": 20})
        stores_res.raise_for_status()
        stores = stores_res.json().get("stores") or []
        print(f"  store search {suburb!r}: {len(stores)} hit(s)")

        ids = list(pick_ids)
        if not ids:
            by_chain: dict[str, dict] = {}
            for s in stores:
                by_chain.setdefault(str(s.get("chain")), s)
            for chain in ("woolworths", "paknsave", "new_world", "freshchoice"):
                if chain in by_chain and len(ids) < 4:
                    ids.append(by_chain[chain]["id"])
            if not ids and stores:
                ids = [stores[0]["id"]]

        print(f"  stores: {', '.join(ids)}")
        print("  save profile ...")
        client.post("/api/profile", json=answers).raise_for_status()

        print("  generate plan ...")
        plan_done = _sse_complete(client, "POST", "/api/plan/generate", timeout=300.0)
        meals = (plan_done.get("meal_plan") or {}).get("meals") or []
        print(f"  plan meals={len(meals)}")

        print("  approve plan ...")
        client.post("/api/plan/approve").raise_for_status()

        print("  resolve shop ...")
        shop_done = _sse_complete(client, "POST", "/api/shop/resolve", timeout=300.0)
        resolved = shop_done.get("resolved_list") or {}
        items = resolved.get("items") or []
        print(f"  shop items={len(items)} total=${resolved.get('total')}")
        if not items:
            raise RuntimeError("empty shop list")

        print("  price-check ...")
        result = _sse_complete(
            client,
            "POST",
            "/api/price-check",
            json_body={"store_ids": ids, "include_split": True},
            timeout=420.0,
        )

    baskets = _basket_stats(result)
    suspects = _suspect_matches(result)
    live_total = sum(b["live"] for b in baskets)
    est_total = sum(b["estimate"] for b in baskets)
    split = result.get("split") or {}

    for b in baskets:
        print(
            f"    [{b['chain']}] {b['name']}: "
            f"live={b['live']}/{b['items']} ({b['live_pct']} pct) "
            f"est={b['estimate']}/{b['items']} ({b['estimate_pct']} pct) "
            f"total=${b['total']}"
        )
    if split:
        print(
            f"  split total=${split.get('total')} "
            f"savings=${split.get('savings_vs_cheapest_single_store')}"
        )

    status = "PASS"
    if live_total < 1:
        status = "FAIL_NO_LIVE"
    elif suspects:
        status = "FAIL_SUSPECT"
        print(f"  SUSPECTS ({len(suspects)}):")
        for s in suspects[:20]:
            print(
                f"    - {s['store']}: {s['ingredient']} -> {s['product']} "
                f"({','.join(s.get('reasons') or [])})"
            )

    summary = {
        "run_index": run_index,
        "chef_id": chef_id,
        "session_id": sid,
        "status": status,
        "shop_items": len(items),
        "shop_total": resolved.get("total"),
        "store_ids": ids,
        "baskets": baskets,
        "live_total": live_total,
        "estimate_total": est_total,
        "suspects": suspects,
        "split_total": split.get("total"),
        "split_savings": split.get("savings_vs_cheapest_single_store"),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "price_check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out_dir / "resolved_list.json").write_text(
        json.dumps(resolved, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  {status} -> {out_dir}")
    return summary


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
    parser.add_argument("--runs", type=int, default=1, help="Number of full E2E runs")
    parser.add_argument("--start-index", type=int, default=1, help="First run index")
    parser.add_argument(
        "--chef",
        default="",
        help="Pin one chef for all runs (default: rotate via CHEF_ORDER)",
    )
    args = parser.parse_args()

    if args.store_ids.strip():
        pick_ids = [s.strip() for s in args.store_ids.split(",") if s.strip()]
    elif args.preset == "chch-central":
        pick_ids = list(CHCH_CENTRAL_STORES)
    else:
        pick_ids = []

    summaries: list[dict] = []
    hard_fail = False
    for i in range(args.runs):
        run_index = args.start_index + i
        chef_id = args.chef or CHEF_ORDER[(run_index - 1) % len(CHEF_ORDER)]
        out_dir = ROOT / "output" / "price-check-smoke" / f"run-{run_index:03d}-{chef_id}"
        try:
            summary = run_once(
                base_url=args.base_url,
                prefs_path=args.prefs,
                suburb=args.suburb,
                pick_ids=pick_ids,
                chef_id=chef_id,
                run_index=run_index,
                out_dir=out_dir,
            )
        except Exception as exc:  # noqa: BLE001 — smoke harness
            print(f"  HARD FAIL: {exc}", file=sys.stderr)
            summary = {
                "run_index": run_index,
                "chef_id": chef_id,
                "status": "FAIL_HARD",
                "error": str(exc),
                "baskets": [],
                "suspects": [],
            }
            hard_fail = True
        summaries.append(summary)
        if summary.get("status") == "FAIL_HARD":
            break

    report_path = ROOT / "output" / "price-check-smoke" / "loop-summary.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"runs": summaries}, indent=2) + "\n", encoding="utf-8")

    print("\n===== LOOP SUMMARY =====")
    print(
        f"{'run':>4}  {'chef':<16}  {'status':<14}  "
        f"{'items':>5}  store live% (est%)"
    )
    for s in summaries:
        baskets = s.get("baskets") or []
        parts = []
        for b in baskets:
            label = (b.get("chain") or "?")[:3]
            parts.append(f"{label}:{b.get('live_pct')}%({b.get('estimate_pct')}%)")
        print(
            f"{s.get('run_index', 0):>4}  {str(s.get('chef_id') or ''):<16}  "
            f"{str(s.get('status') or ''):<14}  "
            f"{int(s.get('shop_items') or 0):>5}  "
            + ("  ".join(parts) if parts else str(s.get('error') or ''))
        )
        for sus in (s.get("suspects") or [])[:8]:
            print(f"       suspect: {sus.get('ingredient')} -> {sus.get('product')}")

    print(f"Wrote {report_path}")

    if hard_fail or any(s.get("status") == "FAIL_HARD" for s in summaries):
        return 1
    if any(s.get("status") == "FAIL_SUSPECT" for s in summaries):
        return 2
    if any(s.get("status") == "FAIL_NO_LIVE" for s in summaries):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
