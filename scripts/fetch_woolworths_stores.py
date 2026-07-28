"""Fetch Woolworths NZ store locations from Overpass into a local JSON cache."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "packages/price_check/src/price_check/data/woolworths_nz_stores.json"

QUERY = """
[out:json][timeout:60];
area["ISO3166-1"="NZ"][admin_level=2]->.nz;
(
  node["shop"="supermarket"]["name"~"Woolworths|Countdown",i](area.nz);
  way["shop"="supermarket"]["name"~"Woolworths|Countdown",i](area.nz);
);
out center tags;
"""


def main() -> None:
    resp = httpx.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": QUERY},
        headers={"User-Agent": "woolworths-meal-agent/0.1 (local store cache)"},
        timeout=90.0,
    )
    resp.raise_for_status()
    elements = resp.json().get("elements") or []
    stores: list[dict] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = str(tags.get("name") or "Woolworths").strip()
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        suburb = str(
            tags.get("addr:suburb")
            or tags.get("addr:city")
            or tags.get("addr:town")
            or ""
        ).strip()
        street = str(tags.get("addr:street") or "").strip()
        housenumber = str(tags.get("addr:housenumber") or "").strip()
        street_line = f"{housenumber} {street}".strip()
        address = ", ".join(x for x in [street_line, suburb] if x)
        key = f"{name}|{suburb}|{street_line}".lower()
        if key in seen:
            continue
        seen.add(key)
        stores.append(
            {
                "name": name.replace("Countdown", "Woolworths"),
                "suburb": suburb,
                "address": address or suburb,
                "lat": lat,
                "lon": lon,
            }
        )
    stores.sort(key=lambda s: (s.get("suburb") or "", s.get("name") or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stores, indent=2), encoding="utf-8")
    print(f"wrote {len(stores)} stores -> {OUT}")


if __name__ == "__main__":
    main()
