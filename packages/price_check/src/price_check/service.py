"""Facade wiring adapters into the price-check engine."""

from __future__ import annotations

from collections.abc import AsyncIterator

from shared.models import GroceryLineItem

from price_check import foodstuffs, freshchoice, woolworths_public
from price_check.directory import get_store
from price_check.engine import (
    basket_for_store,
    compute_split,
    filter_comparable_baskets,
    run_price_check,
)
from price_check.models import (
    PriceCheckLine,
    PriceCheckResult,
    PriceCheckStoreBasket,
    StoreChain,
    StoreRef,
)


async def match_store_item(store: StoreRef, item: GroceryLineItem) -> PriceCheckLine | None:
    if store.chain == StoreChain.WOOLWORTHS:
        return await woolworths_public.match_line(
            store, item.ingredient, float(item.quantity or 1), item.unit or "each"
        )
    if store.chain in (StoreChain.NEW_WORLD, StoreChain.PAKNSAVE):
        return await foodstuffs.match_line(
            store, item.ingredient, float(item.quantity or 1), item.unit or "each"
        )
    if store.chain == StoreChain.FRESHCHOICE:
        return await freshchoice.match_line(
            store, item.ingredient, float(item.quantity or 1), item.unit or "each"
        )
    return None


async def resolve_stores(store_ids: list[str]) -> tuple[list[StoreRef], list[str]]:
    stores: list[StoreRef] = []
    missing: list[str] = []
    seen: set[str] = set()
    for sid in store_ids:
        store = await get_store(sid)
        if store is None:
            missing.append(sid)
            continue
        # Multiple WW branch ids collapse to woolworths:online — dedupe.
        if store.id in seen:
            continue
        seen.add(store.id)
        stores.append(store)
    return stores, missing


async def price_check_for_items(
    *,
    store_ids: list[str],
    items: list[GroceryLineItem],
    include_split: bool = False,
) -> PriceCheckResult:
    stores, missing = await resolve_stores(store_ids)
    if missing and not stores:
        raise ValueError(f"Unknown store id(s): {', '.join(missing)}")
    return await run_price_check(
        stores=stores,
        items=items,
        match_fn=match_store_item,
        include_split=include_split,
    )


async def iter_price_check_baskets(
    *,
    store_ids: list[str],
    items: list[GroceryLineItem],
) -> AsyncIterator[tuple[list[StoreRef], list[str], PriceCheckStoreBasket | None, int]]:
    """Yield ``(stores, missing, basket|None, index)``.

    First yield has ``basket=None`` after stores are resolved; then one yield per basket.
    """
    stores, missing = await resolve_stores(store_ids)
    if missing and not stores:
        raise ValueError(f"Unknown store id(s): {', '.join(missing)}")
    yield stores, missing, None, -1
    for idx, store in enumerate(stores):
        basket = await basket_for_store(store, items, match_store_item)
        yield stores, missing, basket, idx


def finalize_price_check(
    baskets: list[PriceCheckStoreBasket],
    *,
    include_split: bool,
) -> PriceCheckResult:
    kept, skipped = filter_comparable_baskets(baskets)
    split = compute_split(kept) if include_split else None
    ordered = sorted(kept, key=lambda b: (b.total, b.store.name))
    return PriceCheckResult(baskets=ordered, skipped=skipped, split=split)
