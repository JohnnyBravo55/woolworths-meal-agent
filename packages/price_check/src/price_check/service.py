"""Facade wiring adapters into the price-check engine."""

from __future__ import annotations

from shared.models import GroceryLineItem

from price_check import foodstuffs, freshchoice, woolworths_public
from price_check.directory import get_store
from price_check.engine import run_price_check
from price_check.models import PriceCheckLine, PriceCheckResult, StoreChain, StoreRef


async def _match(store: StoreRef, item: GroceryLineItem) -> PriceCheckLine | None:
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


async def price_check_for_items(
    *,
    store_ids: list[str],
    items: list[GroceryLineItem],
    include_split: bool = False,
) -> PriceCheckResult:
    stores: list[StoreRef] = []
    missing: list[str] = []
    for sid in store_ids:
        store = await get_store(sid)
        if store is None:
            missing.append(sid)
        else:
            stores.append(store)
    if missing and not stores:
        raise ValueError(f"Unknown store id(s): {', '.join(missing)}")
    return await run_price_check(
        stores=stores,
        items=items,
        match_fn=_match,
        include_split=include_split,
    )
