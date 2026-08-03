"""FreshChoice Myfoodlink guest catalogue search (login-free HTML search)."""

from __future__ import annotations

import asyncio
import html as html_lib
import re
import time
from typing import Any
from urllib.parse import quote_plus

import httpx

from price_check.links import enrich_line, with_store_url
from price_check.matching import pick_best_product, score_product_name, search_query_variants
from price_check.models import PriceCheckLine, PriceSource, StoreChain, StoreRef
from price_check.pricing import pick_best_priced_product, price_purchase

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_CHOOSER = "https://store.freshchoice.co.nz/"
_CACHE: tuple[float, list[StoreRef]] | None = None
_CACHE_TTL = 6 * 60 * 60

# Curated fallback if the chooser page is unreachable.
_FALLBACK_STORES: list[tuple[str, str, str, str]] = [
    # slug, name, address, suburb
    ("barrington", "FreshChoice Barrington", "256 Barrington Street, Christchurch", "Christchurch"),
    ("citymarket", "FreshChoice Christchurch City Market", "Christchurch City", "Christchurch"),
    ("parklands", "FreshChoice Parklands", "Parklands, Christchurch", "Christchurch"),
    ("edgeware", "FreshChoice Edgeware", "Edgeware, Christchurch", "Christchurch"),
    ("fendalton", "FreshChoice Fendalton", "Fendalton, Christchurch", "Christchurch"),
    ("merivale", "FreshChoice Merivale", "Merivale, Christchurch", "Christchurch"),
    ("sumner", "FreshChoice Sumner", "Sumner, Christchurch", "Christchurch"),
    ("prebbleton", "FreshChoice Prebbleton", "Prebbleton", "Prebbleton"),
    ("cromwell", "FreshChoice Cromwell", "Cromwell", "Cromwell"),
    ("nelsoncity", "FreshChoice Nelson City", "Nelson", "Nelson"),
]

_NAME_START = re.compile(
    r'class="talker__name[^"]*"[^>]*title="(?P<title>[^"]+)"',
    flags=re.I,
)


def _shop_host(slug: str) -> str:
    return f"https://{slug}.store.freshchoice.co.nz"


def _slug_to_name(slug: str) -> str:
    special = {
        "citymarket": "Christchurch City Market",
        "nelsoncity": "Nelson City",
        "central-mall": "Central Mall",
        "hc": "Hornby",
    }
    label = special.get(slug) or slug.replace("-", " ").title()
    return f"FreshChoice {label}"


def _fallback_stores() -> list[StoreRef]:
    return [
        with_store_url(
            StoreRef(
                id=f"freshchoice:{slug}",
                chain=StoreChain.FRESHCHOICE,
                name=name,
                address=address,
                suburb=suburb,
                pricing_note="Live Myfoodlink catalogue prices",
            )
        )
        for slug, name, address, suburb in _FALLBACK_STORES
    ]


async def _resolve_slug(client: httpx.AsyncClient, sid: str) -> StoreRef | None:
    try:
        redirect = await client.get(
            f"https://store.freshchoice.co.nz/{sid}/i_choose_you",
            follow_redirects=False,
        )
    except httpx.HTTPError:
        return None
    loc = redirect.headers.get("location") or ""
    if "supervalue" in loc.lower():
        return None
    m = re.match(r"https?://([a-z0-9-]+)\.store\.freshchoice\.co\.nz/?", loc, re.I)
    if not m:
        return None
    slug = m.group(1).lower()
    suburb = slug.replace("-", " ").title()
    if slug in (
        "citymarket",
        "barrington",
        "parklands",
        "edgeware",
        "fendalton",
        "merivale",
        "sumner",
    ):
        suburb = "Christchurch"
    return with_store_url(
        StoreRef(
            id=f"freshchoice:{slug}",
            chain=StoreChain.FRESHCHOICE,
            name=_slug_to_name(slug),
            address=f"{suburb}, New Zealand",
            suburb=suburb,
            pricing_note="Live Myfoodlink catalogue prices",
        )
    )


async def _discover_stores(client: httpx.AsyncClient) -> list[StoreRef]:
    resp = await client.get(_CHOOSER)
    resp.raise_for_status()
    ids = sorted(set(re.findall(r"/([a-f0-9]{24})/i_choose_you", resp.text)))
    resolved = await asyncio.gather(*(_resolve_slug(client, sid) for sid in ids))
    out = [s for s in resolved if s is not None]
    curated = {s.id: s for s in _fallback_stores()}
    merged: dict[str, StoreRef] = {s.id: s for s in out}
    for sid, store in curated.items():
        if sid not in merged:
            merged[sid] = store
        else:
            merged[sid] = with_store_url(
                StoreRef(
                    id=store.id,
                    chain=store.chain,
                    name=store.name,
                    address=store.address,
                    suburb=store.suburb,
                    latitude=merged[sid].latitude,
                    longitude=merged[sid].longitude,
                    pricing_note=store.pricing_note,
                )
            )
    return sorted(merged.values(), key=lambda s: s.name.lower())


def list_stores() -> list[StoreRef]:
    """Sync list for directory cache warm-path; uses fallback if discovery not cached."""
    global _CACHE
    if _CACHE and _CACHE[0] > time.time():
        return list(_CACHE[1])
    return _fallback_stores()


async def list_stores_async() -> list[StoreRef]:
    global _CACHE
    if _CACHE and _CACHE[0] > time.time():
        return list(_CACHE[1])
    try:
        async with httpx.AsyncClient(timeout=40.0, follow_redirects=True, headers={"User-Agent": _UA}) as client:
            stores = await _discover_stores(client)
        if stores:
            _CACHE = (time.time() + _CACHE_TTL, stores)
            return list(stores)
    except httpx.HTTPError:
        pass
    stores = _fallback_stores()
    _CACHE = (time.time() + _CACHE_TTL, stores)
    return list(stores)


def _parse_products(page_html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _NAME_START.finditer(page_html):
        chunk = page_html[m.start() : m.start() + 3500]
        title = html_lib.unescape(m.group("title") or "").strip()
        name_m = re.search(r'class="talker__product-name">([^<]+)</span>', chunk, flags=re.I)
        if not name_m:
            continue
        name = html_lib.unescape(name_m.group(1)).strip()
        size_m = re.search(r'class="weak size talker__name__size">([^<]*)</span>', chunk, flags=re.I)
        size = html_lib.unescape((size_m.group(1) if size_m else "").strip())
        price_m = re.search(r'class="price__sell"[^>]*>\s*\$(\d+(?:\.\d{2})?)', chunk, flags=re.I)
        if not price_m:
            continue
        try:
            price = float(price_m.group(1))
        except (TypeError, ValueError):
            continue
        sku_m = re.search(r'id="new_order_line_for_([a-f0-9]{24})"', chunk, flags=re.I)
        sku = (sku_m.group(1) if sku_m else "").strip()
        if not name or price <= 0:
            continue
        key = sku or f"{name}|{size}|{price}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": name,
                "brand": "",
                "sku": sku,
                "unit_price": price,
                "size": size,
                "title": title or name,
            }
        )
    return out


async def search_products(store: StoreRef, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
    slug = store.id.split(":", 1)[-1]
    if not slug or not query.strip():
        return []
    url = f"{_shop_host(slug)}/search?q={quote_plus(query.strip())}"
    async with httpx.AsyncClient(timeout=35.0, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        # Warm shop homepage cookies (some stores redirect from bare search).
        await client.get(_shop_host(slug) + "/")
        resp = await client.get(url)
        resp.raise_for_status()
        products = _parse_products(resp.text)
    return products[:limit]


async def match_line(
    store: StoreRef,
    ingredient: str,
    quantity: float,
    unit: str,
    *,
    household_size: int = 2,
) -> PriceCheckLine | None:
    if store.chain != StoreChain.FRESHCHOICE:
        return None
    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in search_query_variants(ingredient):
        batch = await search_products(store, query, limit=12)
        for item in batch:
            key = str(item.get("sku") or "") or f"{item.get('name')}|{item.get('size')}"
            if key in seen:
                continue
            seen.add(key)
            size = str(item.get("size") or "")
            sale_type = "WEIGHT" if size.strip().lower() in {"kg", "kilogram"} else "UNITS"
            products.append({**item, "display": size, "saleType": sale_type})
        if pick_best_product(ingredient, products):
            break
    best = pick_best_priced_product(
        ingredient,
        products,
        quantity=quantity,
        unit=unit,
        score_fn=score_product_name,
        household_size=household_size,
    )
    if not best:
        return None
    unit_price = float(best.get("unit_price") or 0)
    if unit_price <= 0:
        return None
    buy_qty, buy_unit, line_total = price_purchase(
        ingredient=ingredient,
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
        sale_type=str(best.get("saleType") or ""),
        sku=str(best.get("sku") or ""),
        display=str(best.get("display") or best.get("size") or ""),
        product_name=str(best.get("name") or ""),
        household_size=household_size,
    )
    name = " ".join(
        x for x in [best.get("name"), best.get("size")] if x
    ).strip()
    line = PriceCheckLine(
        ingredient=ingredient,
        quantity=buy_qty,
        unit=buy_unit,
        product_name=name,
        sku=str(best.get("sku") or ""),
        unit_price=round(unit_price, 2),
        line_total=line_total,
        price_source=PriceSource.LIVE,
        note="",
    )
    return enrich_line(store, line)
