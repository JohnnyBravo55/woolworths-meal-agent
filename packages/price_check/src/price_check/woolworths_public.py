"""Woolworths NZ anonymous catalogue search for price check."""

from __future__ import annotations

import asyncio
import json
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from price_check.matching import pick_best_product, search_query_variants
from price_check.models import PriceCheckLine, PriceSource, StoreChain, StoreRef

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-NZ,en;q=0.9",
    "x-requested-with": "OnlineShopping_Web",
    "Origin": "https://www.woolworths.co.nz",
    "Referer": "https://www.woolworths.co.nz/",
}
_HOME = "https://www.woolworths.co.nz/"
_SEARCH = "https://www.woolworths.co.nz/api/v1/products"

_DATA_PATH = Path(__file__).with_name("woolworths_nz_stores.json")

# Cap concurrent WW catalogue calls — cloud IPs get throttled when blasted.
_WW_SEM = asyncio.Semaphore(3)
_client_lock = asyncio.Lock()
_shared_client: httpx.AsyncClient | None = None

# Akamai often blocks datacenter IPs (e.g. Render). After a few hard failures,
# stop retrying for this process so multi-store checks stay under gateway limits.
_CIRCUIT_LOCK = asyncio.Lock()
_circuit_open = False
_circuit_failures = 0
_CIRCUIT_THRESHOLD = 1


class WoolworthsCatalogueUnavailable(RuntimeError):
    """Raised when the public catalogue is blocked/unavailable from this host."""


async def _trip_circuit(reason: str) -> None:
    global _circuit_open, _circuit_failures
    async with _CIRCUIT_LOCK:
        _circuit_failures += 1
        if _circuit_failures >= _CIRCUIT_THRESHOLD:
            _circuit_open = True
    raise WoolworthsCatalogueUnavailable(reason)


async def _note_success() -> None:
    global _circuit_open, _circuit_failures
    async with _CIRCUIT_LOCK:
        _circuit_failures = 0
        _circuit_open = False


_PROBE_LOCK = asyncio.Lock()
_probe_ok: bool | None = None
_probe_checked_at = 0.0
_PROBE_TTL_OK = 30 * 60
_PROBE_TTL_FAIL = 10 * 60


def reset_circuit_for_tests() -> None:
    """Test helper — clear process-wide circuit state."""
    global _circuit_open, _circuit_failures, _shared_client, _probe_ok, _probe_checked_at
    _circuit_open = False
    _circuit_failures = 0
    _shared_client = None
    _probe_ok = None
    _probe_checked_at = 0.0


def is_circuit_open() -> bool:
    return _circuit_open


def online_store() -> StoreRef:
    return StoreRef(
        id="woolworths:online",
        chain=StoreChain.WOOLWORTHS,
        name="Woolworths Online",
        address="Nationwide online catalogue",
        suburb="Online",
        pricing_note="Online catalogue prices (login not required)",
    )


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
    """Legacy suburb rows (same online prices). Prefer ``list_stores_for_picker``."""
    stores = [online_store()]
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
    seen: set[str] = set()
    unique: list[StoreRef] = []
    for store in stores:
        if store.id in seen:
            continue
        seen.add(store.id)
        unique.append(store)
    return unique


async def catalogue_reachable() -> bool:
    """Probe whether the public WW catalogue answers from this host."""
    global _probe_ok, _probe_checked_at
    if _circuit_open:
        return False
    now = time.time()
    ttl = _PROBE_TTL_OK if _probe_ok else _PROBE_TTL_FAIL
    if _probe_ok is not None and (now - _probe_checked_at) < ttl:
        return _probe_ok
    async with _PROBE_LOCK:
        now = time.time()
        ttl = _PROBE_TTL_OK if _probe_ok else _PROBE_TTL_FAIL
        if _probe_ok is not None and (now - _probe_checked_at) < ttl:
            return _probe_ok
        try:
            items = await search_products("milk", limit=1)
            _probe_ok = bool(items)
        except Exception:  # noqa: BLE001 — probe must never raise to callers
            _probe_ok = False
        _probe_checked_at = time.time()
        return _probe_ok


async def list_stores_for_picker() -> list[StoreRef]:
    """At most one WW option — prices are nationwide online, not per branch.

    Returns empty when the catalogue is blocked (e.g. Render/Akamai).
    """
    if not await catalogue_reachable():
        return []
    return [online_store()]


def store_from_query(query: str) -> StoreRef | None:
    """Deprecated — synthetic localities are no longer offered."""
    return None


def resolve_store_id(store_id: str) -> StoreRef | None:
    if not store_id.startswith("woolworths:"):
        return None
    if store_id.startswith("woolworths:local:"):
        return None
    # Branch ids all share the online catalogue — normalize to one store.
    return online_store()


async def _get_client() -> httpx.AsyncClient:
    global _shared_client
    async with _client_lock:
        if _shared_client is None or _shared_client.is_closed:
            _shared_client = httpx.AsyncClient(
                # Cloud hosts often stall on Akamai — fail fast for the circuit breaker.
                timeout=httpx.Timeout(12.0, connect=8.0),
                follow_redirects=True,
                headers=_HEADERS,
            )
            # Warm cookies / edge session — helps from cloud IPs.
            try:
                await _shared_client.get(_HOME, headers={**_HEADERS, "Accept": "text/html,*/*"})
            except httpx.HTTPError:
                pass
        return _shared_client


async def search_products(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []
    if _circuit_open:
        raise WoolworthsCatalogueUnavailable(
            "Woolworths catalogue blocked from this host (using estimates)"
        )
    params = {
        "target": "search",
        "search": q,
        "inStockProductsOnly": "false",
        "size": str(min(max(1, limit), 48)),
    }
    last_exc: Exception | None = None
    async with _WW_SEM:
        client = await _get_client()
        for attempt in range(2):
            try:
                resp = await client.get(_SEARCH, params=params, headers=_HEADERS)
                if resp.status_code in (403, 429):
                    await _trip_circuit(f"Woolworths search HTTP {resp.status_code}")
                if resp.status_code in (502, 503):
                    last_exc = httpx.HTTPStatusError(
                        f"Woolworths search HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                    try:
                        await client.get(_HOME, headers={**_HEADERS, "Accept": "text/html,*/*"})
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.35 * (attempt + 1))
                    continue
                resp.raise_for_status()
                try:
                    payload = resp.json()
                except json.JSONDecodeError:
                    await _trip_circuit(
                        f"Woolworths search returned non-JSON ({resp.status_code}): "
                        f"{resp.text[:120]!r}"
                    )
                items = (payload.get("products") or {}).get("items") or []
                await _note_success()
                break
            except WoolworthsCatalogueUnavailable:
                raise
            except httpx.HTTPError as exc:
                last_exc = exc
                await asyncio.sleep(0.35 * (attempt + 1))
                continue
        else:
            assert last_exc is not None
            await _trip_circuit(f"Woolworths search failed: {last_exc!r}")

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
    products: list[dict[str, Any]] = []
    seen_skus: set[str] = set()
    for query in search_query_variants(ingredient):
        batch = await search_products(query, limit=8)
        for item in batch:
            sku = str(item.get("sku") or "")
            if sku and sku in seen_skus:
                continue
            if sku:
                seen_skus.add(sku)
            products.append(item)
        if pick_best_product(ingredient, products):
            break
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
