"""Store directory for price-check branch picker."""

from __future__ import annotations

import asyncio
import re
import time

from price_check import foodstuffs, freshchoice, woolworths_public
from price_check.models import StoreChain, StoreRef

_CACHE: dict[StoreChain, tuple[float, list[StoreRef]]] = {}
_CACHE_TTL = 6 * 60 * 60

# Weak locality words — useful with a city token, not alone.
_WEAK_LOCALITY = frozenset({"central", "city", "north", "south", "east", "west", "upper", "lower"})
_STOP_TOKENS = frozenset({"new", "zealand", "the", "and", "nz"})


def _query_tokens(query: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]+", query.lower())
        if len(t) > 2 and t not in _STOP_TOKENS
    ]


def _store_haystack(store: StoreRef) -> str:
    return f"{store.name} {store.address} {store.suburb} {store.chain.value.replace('_', ' ')}".lower()


def _search_score(store: StoreRef, query: str) -> float:
    """Higher is better. 0 = no match."""
    q = query.strip().lower()
    if not q:
        return 1.0
    hay = _store_haystack(store)
    if q in hay:
        return 100.0
    tokens = _query_tokens(q)
    if not tokens:
        return 0.0
    strong = [t for t in tokens if t not in _WEAK_LOCALITY]
    weak = [t for t in tokens if t in _WEAK_LOCALITY]
    if not strong:
        # e.g. bare "central" — require full phrase already handled above
        return 0.0
    if not all(t in hay for t in strong):
        return 0.0
    score = 40.0 + 15.0 * len(strong)
    score += 10.0 * sum(1 for t in weak if t in hay)
    # Prefer non-synthetic Woolworths locality rows when a real suburb match exists.
    if store.id.startswith("woolworths:local:"):
        score -= 5.0
    return score


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
        scored = [( _search_score(s, q), s) for s in stores]
        stores = [s for score, s in sorted(scored, key=lambda x: -x[0]) if score > 0]
        # Woolworths online catalogue is nationwide — always offer a locality pick
        # when the typed suburb isn't in the static list.
        if chain in (None, StoreChain.WOOLWORTHS) and not any(
            s.chain == StoreChain.WOOLWORTHS for s in stores
        ):
            synthetic = woolworths_public.store_from_query(query)
            if synthetic:
                stores = [synthetic, *stores]
        elif chain == StoreChain.WOOLWORTHS and not any(
            not s.id.startswith("woolworths:local:") for s in stores if s.chain == StoreChain.WOOLWORTHS
        ):
            synthetic = woolworths_public.store_from_query(query)
            if synthetic and all(s.id != synthetic.id for s in stores):
                stores = [synthetic, *stores]
    return stores[:limit]


async def get_store(store_id: str) -> StoreRef | None:
    chain_key = store_id.split(":", 1)[0]
    try:
        chain = StoreChain(chain_key)
    except ValueError:
        return None
    if chain == StoreChain.WOOLWORTHS:
        resolved = woolworths_public.resolve_store_id(store_id)
        if resolved is not None:
            return resolved
    stores = await _load_chain(chain)
    for store in stores:
        if store.id == store_id:
            return store
    return None
