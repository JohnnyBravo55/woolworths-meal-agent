"""Woolworths NZ anonymous catalogue search for price check."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from price_check.matching import pick_best_product
from price_check.models import PriceCheckLine, PriceSource, StoreChain, StoreRef

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json",
    "x-requested-with": "OnlineShopping_Web",
    "Origin": "https://www.woolworths.co.nz",
    "Referer": "https://www.woolworths.co.nz/",
}

_DATA_PATH = Path(__file__).with_name("woolworths_nz_stores.json")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")
    return slug or "local"


@lru_cache(maxsize=1)
def _load_location_rows() -> list[dict[str, Any]]:
    if not _DATA_PATH.exists():
        return []
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return raw if isinstance(raw, list) else []


def list_stores() -> list[StoreRef]:
    stores = [
        StoreRef(
            id="woolworths:online",
            chain=StoreChain.WOOLWORTHS,
            name="Woolworths Online",
            address="Nationwide online catalogue",
            suburb="Online",
            pricing_note="Online catalogue prices (login not required)",
        )
    ]
    for row in _load_location_rows():
        name = str(row.get("name") or "").strip()
        suburb = str(row.get("suburb") or "").strip()
        address = str(row.get("address") or suburb).strip()
        if not name:
            continue
        stores.append(
            StoreRef(
                id=f"woolworths:{_slug(suburb or name)}",
                chain=StoreChain.WOOLWORTHS,
                name=name if name.lower().startswith("woolworths") else f"Woolworths {name}",
                address=address,
                suburb=suburb or address,
                latitude=row.get("lat"),
                longitude=row.get("lon"),
                pricing_note="Online catalogue prices",
            )
        )
    # Deduplicate by id, keep first
    seen: set[str] = set()
    unique: list[StoreRef] = []
    for store in stores:
        if store.id in seen:
            continue
        seen.add(store.id)
        unique.append(store)
    return unique


def store_from_query(query: str) -> StoreRef | None:
    """Build a selectable Woolworths locality from free-text suburb search."""
    q = query.strip()
    if len(q) < 2:
        return None
    label = q.title()
    return StoreRef(
        id=f"woolworths:local:{_slug(q)}",
        chain=StoreChain.WOOLWORTHS,
        name=f"Woolworths {label} (online prices)",
        address=f"{label}, New Zealand",
        suburb=label,
        pricing_note="Online catalogue prices",
    )


def resolve_store_id(store_id: str) -> StoreRef | None:
    if not store_id.startswith("woolworths:"):
        return None
    for store in list_stores():
        if store.id == store_id:
            return store
    if store_id.startswith("woolworths:local:"):
        label = store_id.split(":", 2)[-1].replace("-", " ").title()
        return StoreRef(
            id=store_id,
            chain=StoreChain.WOOLWORTHS,
            name=f"Woolworths {label} (online prices)",
            address=f"{label}, New Zealand",
            suburb=label,
            pricing_note="Online catalogue prices",
        )
    return None


async def search_products(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        resp = await client.get(
            "https://www.woolworths.co.nz/api/v1/products",
            params={
                "target": "search",
                "search": query,
                "inStockProductsOnly": "false",
                "size": str(min(max(1, limit), 48)),
            },
            headers=_HEADERS,
        )
        resp.raise_for_status()
        items = resp.json().get("products", {}).get("items", [])
    out: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") != "Product":
            continue
        price = item.get("price") or {}
        size = item.get("size") or {}
        unit_price = price.get("salePrice") or price.get("originalPrice") or 0
        out.append(
            {
                "name": str(item.get("name") or ""),
                "brand": str(item.get("brand") or ""),
                "sku": str(item.get("sku") or ""),
                "unit_price": float(unit_price or 0),
                "size": str(size.get("volumeSize") or ""),
            }
        )
    return out


async def match_line(store: StoreRef, ingredient: str, quantity: float, unit: str) -> PriceCheckLine | None:
    if store.chain != StoreChain.WOOLWORTHS:
        return None
    products = await search_products(ingredient, limit=8)
    best = pick_best_product(ingredient, products)
    if not best:
        return None
    unit_price = float(best.get("unit_price") or 0)
    if unit_price <= 0:
        return None
    qty = float(quantity or 1) or 1.0
    name = " ".join(x for x in [best.get("brand"), best.get("name"), best.get("size")] if x).strip()
    return PriceCheckLine(
        ingredient=ingredient,
        quantity=qty,
        unit=unit or "each",
        product_name=name,
        sku=str(best.get("sku") or ""),
        unit_price=round(unit_price, 2),
        line_total=round(unit_price * qty, 2),
        price_source=PriceSource.LIVE,
        note="",
    )
