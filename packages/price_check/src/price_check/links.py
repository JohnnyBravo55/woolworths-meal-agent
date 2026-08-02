"""Deep links for assisted shopping (open store / product / search)."""

from __future__ import annotations

from urllib.parse import quote_plus

from price_check.models import PriceCheckLine, StoreChain, StoreRef

_WW_BASE = "https://www.woolworths.co.nz"
_FOODSTUFFS_WEB: dict[StoreChain, str] = {
    StoreChain.NEW_WORLD: "https://www.newworld.co.nz",
    StoreChain.PAKNSAVE: "https://www.paknsave.co.nz",
}


def foodstuffs_web(chain: StoreChain) -> str:
    return _FOODSTUFFS_WEB.get(chain, "")


def freshchoice_host(store_id: str) -> str:
    slug = store_id.split(":", 1)[-1].strip()
    if not slug:
        return "https://store.freshchoice.co.nz"
    return f"https://{slug}.store.freshchoice.co.nz"


def store_url_for(store: StoreRef) -> str:
    if store.store_url:
        return store.store_url
    if store.chain == StoreChain.WOOLWORTHS:
        return _WW_BASE
    if store.chain in _FOODSTUFFS_WEB:
        return _FOODSTUFFS_WEB[store.chain]
    if store.chain == StoreChain.FRESHCHOICE:
        return freshchoice_host(store.id)
    return ""


def woolworths_product_url(sku: str) -> str:
    sku = (sku or "").strip()
    if not sku or sku in ("OFFLINE", "PANTRY"):
        return ""
    return f"{_WW_BASE}/shop/productdetails?stockcode={quote_plus(sku)}"


def woolworths_search_url(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return _WW_BASE
    return f"{_WW_BASE}/shop/search?searchTerm={quote_plus(q)}"


def foodstuffs_product_url(chain: StoreChain, product_id: str) -> str:
    web = foodstuffs_web(chain)
    pid = (product_id or "").strip()
    if not web or not pid:
        return ""
    # Edge product pages accept /shop/product/{id}; slug suffix is optional.
    return f"{web}/shop/product/{quote_plus(pid)}"


def foodstuffs_search_url(chain: StoreChain, query: str) -> str:
    web = foodstuffs_web(chain)
    q = (query or "").strip()
    if not web:
        return ""
    if not q:
        return web
    return f"{web}/shop/search?q={quote_plus(q)}"


def freshchoice_search_url(store_id: str, query: str) -> str:
    host = freshchoice_host(store_id)
    q = (query or "").strip()
    if not q:
        return host
    return f"{host}/search?q={quote_plus(q)}"


def search_url_for(store: StoreRef, query: str) -> str:
    if store.chain == StoreChain.WOOLWORTHS:
        return woolworths_search_url(query)
    if store.chain in _FOODSTUFFS_WEB:
        return foodstuffs_search_url(store.chain, query)
    if store.chain == StoreChain.FRESHCHOICE:
        return freshchoice_search_url(store.id, query)
    return ""


def product_url_for(store: StoreRef, *, sku: str, product_name: str = "") -> str:
    if store.chain == StoreChain.WOOLWORTHS:
        return woolworths_product_url(sku) or (
            woolworths_search_url(product_name) if product_name else ""
        )
    if store.chain in _FOODSTUFFS_WEB:
        return foodstuffs_product_url(store.chain, sku)
    # FreshChoice guest HTML does not expose stable PDP URLs today.
    return ""


def with_store_url(store: StoreRef) -> StoreRef:
    if store.store_url:
        return store
    url = store_url_for(store)
    if not url:
        return store
    return store.model_copy(update={"store_url": url})


def enrich_line(store: StoreRef, line: PriceCheckLine) -> PriceCheckLine:
    """Fill product_url / search_url when adapters omitted them."""
    query = (line.product_name or line.ingredient or "").strip()
    product_url = (line.product_url or "").strip() or product_url_for(
        store, sku=line.sku, product_name=query
    )
    search_url = (line.search_url or "").strip() or search_url_for(
        store, query or line.ingredient
    )
    updates: dict[str, str] = {}
    if product_url and product_url != line.product_url:
        updates["product_url"] = product_url
    if search_url and search_url != line.search_url:
        updates["search_url"] = search_url
    return line.model_copy(update=updates) if updates else line
