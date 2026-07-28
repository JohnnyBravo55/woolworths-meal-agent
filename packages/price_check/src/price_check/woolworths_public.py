"""Woolworths NZ anonymous catalogue search for price check."""

from __future__ import annotations

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

# Online catalogue is fulfilment-based; expose named hubs for picker UX.
_WOOLWORTHS_HUBS: list[StoreRef] = [
    StoreRef(
        id="woolworths:online",
        chain=StoreChain.WOOLWORTHS,
        name="Woolworths Online",
        address="Nationwide online catalogue",
        suburb="Online",
        pricing_note="Online catalogue prices (login not required)",
    ),
    StoreRef(
        id="woolworths:auckland",
        chain=StoreChain.WOOLWORTHS,
        name="Woolworths Auckland (online prices)",
        address="Auckland region online catalogue",
        suburb="Auckland",
        pricing_note="Online catalogue prices",
    ),
    StoreRef(
        id="woolworths:wellington",
        chain=StoreChain.WOOLWORTHS,
        name="Woolworths Wellington (online prices)",
        address="Wellington region online catalogue",
        suburb="Wellington",
        pricing_note="Online catalogue prices",
    ),
    StoreRef(
        id="woolworths:christchurch",
        chain=StoreChain.WOOLWORTHS,
        name="Woolworths Christchurch (online prices)",
        address="Christchurch region online catalogue",
        suburb="Christchurch",
        pricing_note="Online catalogue prices",
    ),
    StoreRef(
        id="woolworths:hamilton",
        chain=StoreChain.WOOLWORTHS,
        name="Woolworths Hamilton (online prices)",
        address="Hamilton region online catalogue",
        suburb="Hamilton",
        pricing_note="Online catalogue prices",
    ),
]


def list_stores() -> list[StoreRef]:
    return list(_WOOLWORTHS_HUBS)


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
