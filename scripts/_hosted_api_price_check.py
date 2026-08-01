#!/usr/bin/env python3
"""API-only hosted price-check verification against Render."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = "https://mealagent.pyxstudio.nz"
CODE = "usertest1"
STORES = [
    "woolworths:christchurch",
    "new_world:c1aaac72-38c0-4cc0-ad05-f241047d88c5",
    "paknsave:61dd754e-8525-4b9e-9e08-173389eea8a8",
    "freshchoice:citymarket",
]
OUT = ROOT / "output" / "hosted-api-price-check.json"


def sse(client: httpx.Client, method: str, path: str, timeout: float = 300.0) -> dict:
    complete = None
    with client.stream(method, path, timeout=timeout) as resp:
        print(path, resp.status_code)
        resp.raise_for_status()
        event = "message"
        data: list[str] = []
        for raw in resp.iter_lines():
            line = raw.decode() if isinstance(raw, bytes) else raw
            if line == "":
                if data:
                    payload = json.loads("\n".join(data))
                    if event == "complete":
                        complete = payload
                    elif event == "error":
                        raise RuntimeError(str(payload))
                event = "message"
                data = []
                continue
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip())
    if not complete:
        raise RuntimeError(f"no complete for {path}")
    return complete


def main() -> int:
    prefs = json.loads((ROOT / "profiles" / "web_smoke_prefs.json").read_text(encoding="utf-8"))
    answers = {k: v for k, v in prefs.items() if k != "name"}
    answers["chef_id"] = "basic_sam"
    answers["store_name"] = "Christchurch Central"

    with httpx.Client(
        base_url=API,
        headers={"X-Access-Code": CODE, "Content-Type": "application/json"},
        timeout=120.0,
        follow_redirects=True,
    ) as client:
        r = client.post("/api/session/start")
        print("session", r.status_code)
        r.raise_for_status()
        client.headers["X-Session-Id"] = r.json()["session_id"]
        client.post("/api/profile", json=answers).raise_for_status()

        stores = client.get("/api/stores/search", params={"q": "Christchurch Central", "limit": 20})
        print("stores", stores.status_code, len(stores.json().get("stores") or []))
        for s in (stores.json().get("stores") or [])[:10]:
            print(" ", s.get("chain"), s.get("id"), s.get("name"), "|", s.get("pricing_note"))

        print("plan...")
        sse(client, "POST", "/api/plan/generate")
        client.post("/api/plan/approve").raise_for_status()
        print("shop...")
        shop = sse(client, "POST", "/api/shop/resolve")
        n = len((shop.get("resolved_list") or {}).get("items") or [])
        print("items", n)
        if n < 1:
            print("FAIL empty shop", file=sys.stderr)
            return 1

        print("price-check...")
        pc = client.post(
            "/api/price-check",
            json={"store_ids": STORES, "include_split": True},
            timeout=240.0,
        )
        print("pc", pc.status_code)
        if pc.status_code >= 400:
            print(pc.text[:1200], file=sys.stderr)
            return 1
        result = pc.json()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        issues: list[str] = []
        for b in result.get("baskets") or []:
            s = b.get("store") or {}
            live = int(b.get("live_count") or 0)
            est = int(b.get("estimate_count") or 0)
            tot = live + est
            pct = round(100 * live / tot, 1) if tot else 0
            note = str(s.get("pricing_note") or "")
            print(
                f"[{s.get('chain')}] {s.get('name')}: live={live}/{tot} ({pct}%) "
                f"est={est} note={note!r} warning={b.get('warning')!r}"
            )
            if "not wired" in note.lower():
                issues.append(f"{s.get('name')}: still estimate-only ({note})")
            if live < 1:
                issues.append(f"{s.get('name')}: zero live matches")
            if s.get("chain") == "freshchoice" and pct < 40:
                issues.append(f"FreshChoice live rate low: {pct}%")

        if len(result.get("baskets") or []) < 4:
            issues.append(f"expected 4 baskets, got {len(result.get('baskets') or [])}")

        if issues:
            print("FAIL:", file=sys.stderr)
            for i in issues:
                print(" -", i, file=sys.stderr)
            return 2
        print(f"PASS -> {OUT}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
