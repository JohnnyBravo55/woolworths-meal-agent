"""Foodstuffs Edge guest client (New World + Pak'nSave)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from price_check.links import enrich_line, with_store_url
from price_check.matching import pick_best_product, score_product_name, search_query_variants
from price_check.models import PriceCheckLine, PriceSource, StoreChain, StoreRef
from price_check.pricing import pick_best_priced_product, price_purchase

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_CHAIN_CONFIG: dict[StoreChain, dict[str, str]] = {
    StoreChain.NEW_WORLD: {
        "web": "https://www.newworld.co.nz",
        "api": "https://api-prod.newworld.co.nz/v1/edge",
        "banner": "MNW",
    },
    StoreChain.PAKNSAVE: {
        "web": "https://www.paknsave.co.nz",
        "api": "https://api-prod.paknsave.co.nz/v1/edge",
        "banner": "PNS",
    },
}

_token_cache: dict[StoreChain, tuple[str, float]] = {}


def _cfg(chain: StoreChain) -> dict[str, str]:
    if chain not in _CHAIN_CONFIG:
        raise ValueError(f"Unsupported Foodstuffs chain: {chain}")
    return _CHAIN_CONFIG[chain]


async def get_guest_token(chain: StoreChain, client: httpx.AsyncClient | None = None) -> str:
    cached = _token_cache.get(chain)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    cfg = _cfg(chain)
    own = client is None
    client = client or httpx.AsyncClient(timeout=25.0, follow_redirects=True)
    try:
        resp = await client.post(
            f"{cfg['web']}/api/user/get-current-user",
            json={"fingerprintUser": "meal-agent", "fingerprintGuest": _UA},
            headers={
                "Origin": cfg["web"],
                "Referer": f"{cfg['web']}/",
                "User-Agent": _UA,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError(f"No guest token from {chain.value}")
        _token_cache[chain] = (token, time.time() + 25 * 60)
        return token
    finally:
        if own:
            await client.aclose()


async def list_stores(chain: StoreChain) -> list[StoreRef]:
    cfg = _cfg(chain)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        token = await get_guest_token(chain, client)
        resp = await client.get(
            f"{cfg['api']}/store",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": cfg["web"],
                "User-Agent": _UA,
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        raw = resp.json().get("stores") or []
    out: list[StoreRef] = []
    for s in raw:
        sid = str(s.get("id") or "")
        if not sid:
            continue
        name = str(s.get("name") or "Store")
        address = str(s.get("address") or "")
        suburb = ""
        if "," in address:
            parts = [p.strip() for p in address.split(",")]
            if len(parts) >= 2:
                suburb = parts[-2] if parts[-1].isdigit() or parts[-1][:1].isdigit() else parts[-1]
                if parts[-1].replace(" ", "").isdigit() or any(ch.isdigit() for ch in parts[-1]):
                    suburb = parts[-2] if len(parts) >= 2 else parts[0]
        out.append(
            with_store_url(
                StoreRef(
                    id=f"{chain.value}:{sid}",
                    chain=chain,
                    name=name,
                    address=address,
                    suburb=suburb,
                    latitude=s.get("latitude"),
                    longitude=s.get("longitude"),
                    pricing_note="Live in-store / online catalogue prices",
                )
            )
        )
    return out


def _search_payload(query: str, store_uuid: str, limit: int = 8) -> dict[str, Any]:
    return {
        "algoliaQuery": {
            "attributesToHighlight": [],
            "attributesToRetrieve": [
                "productID",
                "Type",
                "sponsored",
                "category0NI",
                "category1NI",
                "category2NI",
            ],
            "facets": ["brand", "category1NI", "onPromotion", "productFacets", "tobacco"],
            "filters": f"stores:{store_uuid}",
            "hitsPerPage": limit,
            "page": 0,
            "query": query,
            "analyticsTags": ["fs#WEB:desktop"],
        },
        "algoliaFacetQueries": [],
        "storeId": store_uuid,
        "hitsPerPage": limit,
        "page": 0,
        "sortOrder": "NI_POPULARITY_ASC",
        "tobaccoQuery": True,
        "precisionMedia": {
            "adDomain": "SEARCH_PAGE",
            "adPositions": [4, 8, 12],
            "publishImpressionEvent": False,
            "disableAds": False,
        },
    }


def _cents_to_nzd(value: Any) -> float:
    try:
        return round(int(value) / 100.0, 2)
    except (TypeError, ValueError):
        return 0.0


async def search_products(chain: StoreChain, store_uuid: str, query: str, *, limit: int = 8) -> list[dict]:
    cfg = _cfg(chain)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        token = await get_guest_token(chain, client)
        resp = await client.post(
            f"{cfg['api']}/search/paginated/products",
            json=_search_payload(query, store_uuid, limit=limit),
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": cfg["web"],
                "User-Agent": _UA,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return list(resp.json().get("products") or [])


def _effective_cents(product: dict) -> int | None:
    """Prefer Club Deal / promo cents when cheaper than shelf price."""
    single = product.get("singlePrice") or {}
    shelf = single.get("price")
    promo_cents = None
    for promo in product.get("promotions") or []:
        if not isinstance(promo, dict):
            continue
        reward = promo.get("rewardValue")
        if reward is None:
            continue
        try:
            value = int(reward)
        except (TypeError, ValueError):
            continue
        if promo_cents is None or value < promo_cents:
            promo_cents = value
    try:
        shelf_i = int(shelf) if shelf is not None else None
    except (TypeError, ValueError):
        shelf_i = None
    if shelf_i is None:
        return promo_cents
    if promo_cents is None:
        return shelf_i
    return min(shelf_i, promo_cents)


async def match_line(store: StoreRef, ingredient: str, quantity: float, unit: str) -> PriceCheckLine | None:
    if store.chain not in _CHAIN_CONFIG:
        return None
    store_uuid = store.id.split(":", 1)[-1]
    candidates: list[dict] = []
    seen_skus: set[str] = set()
    for query in search_query_variants(ingredient):
        products = await search_products(store.chain, store_uuid, query, limit=8)
        for p in products:
            sku = str(p.get("productId") or "")
            if sku and sku in seen_skus:
                continue
            if sku:
                seen_skus.add(sku)
            cents = _effective_cents(p)
            candidates.append(
                {
                    "name": str(p.get("name") or p.get("displayName") or ""),
                    "brand": str(p.get("brand") or ""),
                    "sku": sku,
                    "price_cents": cents,
                    "display": str(p.get("displayName") or ""),
                    "saleType": str(p.get("saleType") or ""),
                    "raw": p,
                }
            )
        if pick_best_product(ingredient, candidates):
            break
    best = pick_best_priced_product(
        ingredient,
        candidates,
        quantity=quantity,
        unit=unit,
        score_fn=score_product_name,
    )
    if not best:
        return None
    unit_price = _cents_to_nzd(best.get("price_cents"))
    if unit_price <= 0:
        return None
    buy_qty, buy_unit, line_total = price_purchase(
        ingredient=ingredient,
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
        sale_type=str(best.get("saleType") or ""),
        sku=str(best.get("sku") or ""),
        display=str(best.get("display") or ""),
        product_name=str(best.get("name") or ""),
    )
    product_name = " ".join(
        x for x in [best.get("brand"), best.get("name"), best.get("display")] if x
    ).strip()
    line = PriceCheckLine(
        ingredient=ingredient,
        quantity=buy_qty,
        unit=buy_unit,
        product_name=product_name,
        sku=str(best.get("sku") or ""),
        unit_price=unit_price,
        line_total=line_total,
        price_source=PriceSource.LIVE,
        note="",
    )
    return enrich_line(store, line)
