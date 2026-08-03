#!/usr/bin/env python3
"""Plan → WW online shop list → competitor price-check, with accuracy audit.

Checks:
  - Shop list uses live WW SKUs (not OFFLINE estimates)
  - Unit/line prices are household-sane
  - Product names match ingredients (score_product_name)
  - Spot-check catalogue prices still match live public API
  - Competitor compare baskets are sane vs WW shop total
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "price_check" / "src"))

from price_check.matching import score_product_name  # noqa: E402

API = "http://127.0.0.1:8000"
PREFS = ROOT / "profiles" / "web_smoke_prefs.json"
OUT = ROOT / "output" / "ww-shop-list-accuracy"
STORES = [
    "new_world:c1aaac72-38c0-4cc0-ad05-f241047d88c5",
    "paknsave:61dd754e-8525-4b9e-9e08-173389eea8a8",
    "freshchoice:citymarket",
]

UNIT_CAPS = {
    "salmon": 55,
    "chicken": 30,
    "beef": 35,
    "pork": 30,
    "lamb": 40,
    "mince": 30,
    "rice": 20,  # multi-kg jasmine/basmati bags are normal
    "milk": 10,
    "egg": 15,
    "oil": 20,
    "butter": 12,
    "cheese": 20,
    "honey": 20,
}


def sse(client: httpx.Client, method: str, path: str, *, timeout: float = 420.0, json_body=None) -> dict:
    complete = None
    errors: list[str] = []
    with client.stream(method, path, json=json_body, timeout=timeout) as resp:
        print(path, resp.status_code)
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
                        print(" ", msg)
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


def live_ww_price(sku: str, product_name: str) -> float | None:
    """Fetch current catalogue price for a SKU via public search on product name."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "x-requested-with": "OnlineShopping_Web",
        "Origin": "https://www.woolworths.co.nz",
        "Referer": "https://www.woolworths.co.nz/",
    }
    q = " ".join((product_name or "").split()[:6]) or sku
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as c:
            r = c.get(
                "https://www.woolworths.co.nz/api/v1/products",
                params={
                    "target": "search",
                    "search": q,
                    "inStockProductsOnly": "false",
                    "size": "24",
                },
            )
            r.raise_for_status()
            items = (r.json().get("products") or {}).get("items") or []
            for item in items:
                if str(item.get("sku") or "") != str(sku):
                    continue
                price = item.get("price") or {}
                return float(price.get("salePrice") or price.get("originalPrice") or 0) or None
    except Exception as exc:  # noqa: BLE001
        print(f"  live lookup failed for {sku}: {exc}")
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prefs = json.loads(PREFS.read_text(encoding="utf-8"))
    answers = {k: v for k, v in prefs.items() if k != "name"}
    answers["chef_id"] = "basic_sam"
    answers["store_name"] = "Christchurch Central"

    issues: list[str] = []

    with httpx.Client(base_url=API, timeout=120.0, follow_redirects=True) as client:
        r = client.post("/api/session/start")
        r.raise_for_status()
        sid = r.json()["session_id"]
        client.headers["X-Session-Id"] = sid
        print("session", sid[:8])
        client.post("/api/profile", json=answers).raise_for_status()

        print("plan…")
        sse(client, "POST", "/api/plan/generate")
        client.post("/api/plan/approve").raise_for_status()

        print("shop (WW online catalogue)…")
        shop = sse(client, "POST", "/api/shop/resolve")
        resolved = shop.get("resolved_list") or {}
        items = list(resolved.get("items") or [])
        shop_total = float(resolved.get("total") or 0)
        (OUT / "resolved_list.json").write_text(
            json.dumps(resolved, indent=2) + "\n", encoding="utf-8"
        )
        print(f"  items={len(items)} total=${shop_total:.2f}")

        if not items:
            print("FAIL empty shop list", file=sys.stderr)
            return 1

        offline = [i for i in items if str(i.get("sku") or "") in {"", "OFFLINE"} or not i.get("in_stock", True) and str(i.get("sku")) == "OFFLINE"]
        offline = [i for i in items if str(i.get("sku") or "") in {"", "OFFLINE"}]
        print(f"  offline/missing sku={len(offline)}")
        if len(offline) > max(2, len(items) // 5):
            issues.append(f"too many offline/estimate lines: {len(offline)}/{len(items)}")

        print("\n=== SHOP LIST (WW online) ===")
        spot: list[dict] = []
        for item in items:
            ing = str(item.get("ingredient") or "")
            name = str(item.get("product_name") or "")
            sku = str(item.get("sku") or "")
            unit = float(item.get("unit_price") or 0)
            line = float(item.get("line_total") or 0)
            qty = float(item.get("quantity") or 1)
            print(f"  {ing}: {name} sku={sku} qty={qty:g} unit=${unit:.2f} line=${line:.2f}")

            if sku in {"", "OFFLINE"}:
                issues.append(f"offline: {ing}")
                continue

            score = score_product_name(ing, name)
            if score <= 0:
                issues.append(f"bad match ({score}): {ing} -> {name}")

            cap = 35.0
            for key, val in UNIT_CAPS.items():
                if key in ing.lower():
                    cap = val
                    break
            if unit > cap:
                issues.append(f"high unit ${unit:.2f} (>${cap}): {ing} -> {name}")
            if line > 45:
                issues.append(f"high line ${line:.2f}: {ing} -> {name}")
            if unit <= 0 or line <= 0:
                issues.append(f"non-positive price: {ing}")

            if len(spot) < 6 and any(
                k in ing.lower() for k in ("chicken", "beef", "milk", "rice", "salmon", "mince", "egg")
            ):
                spot.append(item)

        print("\n=== LIVE CATALOGUE SPOT-CHECK ===")
        for item in spot:
            sku = str(item.get("sku"))
            name = str(item.get("product_name") or "")
            listed = float(item.get("unit_price") or 0)
            live = live_ww_price(sku, name)
            if live is None:
                issues.append(f"could not re-fetch live price for {sku} ({item.get('ingredient')})")
                print(f"  {sku}: listed=${listed:.2f} live=MISSING")
                continue
            delta = abs(live - listed)
            ok = delta <= 0.05 or delta / max(live, 0.01) <= 0.02
            print(f"  {sku}: listed=${listed:.2f} live=${live:.2f} delta=${delta:.2f} {'OK' if ok else 'DRIFT'}")
            if not ok:
                issues.append(
                    f"price drift {item.get('ingredient')}: listed ${listed:.2f} vs live ${live:.2f}"
                )

        print("\n=== COMPETITOR PRICE CHECK ===")
        pc = sse(
            client,
            "POST",
            "/api/price-check",
            json_body={"store_ids": STORES, "include_split": True},
            timeout=420.0,
        )
        (OUT / "price_check.json").write_text(json.dumps(pc, indent=2) + "\n", encoding="utf-8")
        for b in pc.get("baskets") or []:
            s = b.get("store") or {}
            live_n = int(b.get("live_count") or 0)
            est_n = int(b.get("estimate_count") or 0)
            tot = float(b.get("total") or 0)
            print(
                f"  [{s.get('chain')}] {s.get('name')}: ${tot:.2f} "
                f"live={live_n}/{live_n + est_n}"
            )
            if live_n < 1:
                issues.append(f"{s.get('name')}: zero live matches")
            # Competitor baskets shouldn't be wildly below WW if WW is real catalogue
            # (can be cheaper — allow up to ~70% lower; flag if < 25% of WW = likely broken)
            if shop_total > 40 and tot < shop_total * 0.25:
                issues.append(
                    f"{s.get('name')} total ${tot:.2f} implausibly low vs WW shop ${shop_total:.2f}"
                )
            if tot > shop_total * 3 and shop_total > 40:
                issues.append(
                    f"{s.get('name')} total ${tot:.2f} implausibly high vs WW shop ${shop_total:.2f}"
                )
            for line in b.get("lines") or []:
                if float(line.get("unit_price") or 0) > 55:
                    issues.append(
                        f"compare high unit ${line.get('unit_price')}: "
                        f"{s.get('chain')} {line.get('ingredient')} -> {line.get('product_name')}"
                    )

        for sk in pc.get("skipped") or []:
            print(f"  skipped: {(sk.get('store') or {}).get('name')}: {sk.get('reason')}")

    summary = {
        "shop_total": shop_total,
        "shop_items": len(items),
        "offline": len(offline),
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
