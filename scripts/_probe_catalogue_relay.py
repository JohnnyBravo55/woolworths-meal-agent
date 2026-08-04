"""Probe hosted catalogue browser-relay path without the UI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PREFS = json.loads((ROOT / "profiles" / "web_smoke_prefs.json").read_text(encoding="utf-8"))
API = "https://mealagent.pyxstudio.nz"
ACCESS = "usertest1"
PROXY = "https://ww-catalogue-proxy.modern-borogovia.workers.dev"


def main() -> int:
    h = {"X-Access-Code": ACCESS, "Content-Type": "application/json"}
    with httpx.Client(timeout=120.0, headers=h) as client:
        sid = client.post(f"{API}/api/session/start", json={}).json()["session_id"]
        h["X-Session-Id"] = sid
        client.headers.update(h)

        # Minimal profile + plan path reused from smoke prefs
        client.post(f"{API}/api/profile", json=PREFS)
        client.post(f"{API}/api/chef/select", json={"chef_id": PREFS.get("chef_id", "basic_sam")})

        # Generate plan via SSE
        with client.stream("POST", f"{API}/api/plan/generate") as resp:
            for line in resp.iter_lines():
                if line.startswith("event: complete"):
                    break
                if line.startswith("event: error"):
                    print("plan error", line)
                    return 1

        client.post(f"{API}/api/plan/approve")
        q = client.get(f"{API}/api/shop/catalogue-queries").json()
        queries = q.get("queries") or []
        proxy_candidates = [
            (q.get("proxy_url") or "").rstrip("/"),
            PROXY,
        ]
        proxy = ""
        for candidate in proxy_candidates:
            if not candidate:
                continue
            try:
                if client.get(f"{candidate}/health").status_code == 200:
                    proxy = candidate
                    break
            except Exception:
                continue
        print("queries", len(queries), "proxy", proxy)
        if not proxy:
            print("no live proxy")
            return 1

        hits: dict[str, dict] = {}
        for query in queries:
            try:
                r = client.get(f"{proxy}/search", params={"q": query, "size": "8"})
            except Exception as exc:
                print("search_err", query, exc)
                continue
            if r.status_code == 200 and "products" in r.text:
                hits[query] = r.json()
        print("fetched_hits", len(hits), "of", len(queries))
        up = client.post(f"{API}/api/shop/catalogue-hits", json={"hits": hits}).json()
        print("uploaded", up)

        # Resolve SSE
        with client.stream("POST", f"{API}/api/shop/resolve?force=true") as resp:
            body = ""
            for line in resp.iter_lines():
                body += line + "\n"
                if line.startswith("event: complete") or line.startswith("event: error"):
                    # read data line next iterations
                    pass
            print("resolve_tail", body[-400:])

        shop = client.get(f"{API}/api/shop/list").json()
        resolved = shop.get("resolved_list") or shop
        items = resolved.get("items") or []
        offline = sum(1 for i in items if i.get("sku") in (None, "", "OFFLINE"))
        print("items", len(items), "offline", offline, "real", len(items) - offline)
        for i in items[:8]:
            print(i.get("sku"), i.get("ingredient"), (i.get("product_name") or "")[:50])
        return 0 if items and offline < len(items) else 2


if __name__ == "__main__":
    sys.exit(main())
