"""Store directory for price-check branch picker."""

from __future__ import annotations

import asyncio
import time

from price_check import foodstuffs, freshchoice, woolworths_public
from price_check.models import StoreChain, StoreRef

_CACHE: dict[StoreChain, tuple[float, list[StoreRef]]] = {}
_CACHE_TTL = 6 * 60 * 60


async def _load_chain(chain: StoreChain) -> list[StoreRef]:
    cached = _CACHE.get(chain)
    if cached and cached[0] > time.time():
        return cached[1]
    if chain == StoreChain.WOOLWORTHS:
        stores = woolworths_public.list_stores()
    elif chain == StoreChain.FRESHCHOICE:
        stores = freshchoice.list_stores()
    elif chain in (StoreChain.NEW_WORLD, StoreChain.PAKNSAVE):
        stores = await foodstuffs.list_stores(chain)
    else:
        stores = []
    _CACHE[chain] = (time.time() + _CACHE_TTL, stores)
    return stores


async def all_stores(*, chains: list[StoreChain] | None = None) -> list[StoreRef]:
    selected = chains or list(StoreChain)
    chunks = await asyncio.gather(*(_load_chain(c) for c in selected), return_exceptions=True)
    out: list[StoreRef] = []
    for chain, chunk in zip(selected, chunks, strict=True):
        if isinstance(chunk, Exception):
            continue
        out.extend(chunk)
    return out


async def search_stores(query: str = "", chain: StoreChain | None = None, *, limit: int = 40) -> list[StoreRef]:
    chains = [chain] if chain else None
    stores = await all_stores(chains=chains)
    q = query.strip().lower()
    if q:
        stores = [
            s
            for s in stores
            if q in s.name.lower()
            or q in s.address.lower()
            or q in s.suburb.lower()
            or q in s.chain.value.replace("_", " ")
        ]
    return stores[:limit]


async def get_store(store_id: str) -> StoreRef | None:
    chain_key = store_id.split(":", 1)[0]
    try:
        chain = StoreChain(chain_key)
    except ValueError:
        return None
    stores = await _load_chain(chain)
    for store in stores:
        if store.id == store_id:
            return store
    return None
