"""Price-check engine: per-store baskets + optional smart split."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from shared.models import GroceryLineItem
from woolworths_adapter.estimates import estimate_price

from price_check.links import enrich_line, with_store_url
from price_check.models import (
    PriceCheckLine,
    PriceCheckResult,
    PriceCheckSkippedStore,
    PriceCheckStoreBasket,
    PriceSource,
    PriceSplitAssignment,
    PriceSplitResult,
    StoreRef,
)

MatchFn = Callable[[StoreRef, GroceryLineItem], Awaitable[PriceCheckLine | None]]

# Cap concurrent catalogue lookups across stores (avoids WW/Foodstuffs rate spikes).
_MATCH_SEM = asyncio.Semaphore(8)


def _estimate_line(store: StoreRef, item: GroceryLineItem, *, note: str) -> PriceCheckLine:
    """Prefer shop-list unit/line totals; fall back to heuristic estimate."""
    unit_price = float(item.unit_price or 0)
    line_total = float(item.line_total or 0)
    if unit_price <= 0 and line_total <= 0:
        unit_price = estimate_price(item.ingredient)
        qty = float(item.quantity or 1) or 1.0
        line_total = round(unit_price * qty, 2)
    elif line_total <= 0:
        qty = float(item.quantity or 1) or 1.0
        line_total = round(unit_price * qty, 2)
    elif unit_price <= 0:
        qty = float(item.quantity or 1) or 1.0
        unit_price = round(line_total / qty, 2) if qty else line_total
    line = PriceCheckLine(
        ingredient=item.ingredient,
        quantity=float(item.quantity or 1),
        unit=item.unit or "each",
        product_name=item.product_name or item.ingredient,
        sku=(
            ""
            if str(item.sku or "").strip() in ("", "OFFLINE", "PANTRY")
            else str(item.sku).strip()
        ),
        unit_price=round(unit_price, 2),
        line_total=round(line_total, 2),
        price_source=PriceSource.ESTIMATE,
        note=note,
        product_url=str(item.product_url or ""),
    )
    return enrich_line(store, line)


async def _match_one(
    store: StoreRef,
    item: GroceryLineItem,
    match_fn: MatchFn,
) -> PriceCheckLine | None | BaseException:
    async with _MATCH_SEM:
        try:
            return await match_fn(store, item)
        except Exception as exc:  # noqa: BLE001 — per-line fallback to estimate
            return exc


async def basket_for_store(
    store: StoreRef,
    items: list[GroceryLineItem],
    match_fn: MatchFn,
) -> PriceCheckStoreBasket:
    store = with_store_url(store)
    lines: list[PriceCheckLine] = []
    warning = ""
    matched = await asyncio.gather(*(_match_one(store, item, match_fn) for item in items))
    errors = [m for m in matched if isinstance(m, BaseException)]
    if errors and len(errors) == len(items):
        msg = str(errors[0]).strip() or type(errors[0]).__name__
        if "Woolworths" in type(errors[0]).__name__ or "Woolworths" in msg:
            warning = "Woolworths live catalogue isn't reachable from this server."
        else:
            warning = f"Live pricing unavailable ({msg})."
    elif errors:
        msg = str(errors[0]).strip() or type(errors[0]).__name__
        warning = f"{len(errors)} live lookup(s) failed ({msg}); those lines use estimates."

    for item, live in zip(items, matched, strict=True):
        if isinstance(live, BaseException):
            note = "estimate — live pricing unavailable for this store"
            lines.append(_estimate_line(store, item, note=note))
        elif live is not None and live.price_source == PriceSource.LIVE and live.line_total > 0:
            lines.append(enrich_line(store, live))
        else:
            note = "estimate — not found at this store"
            if live is not None and live.note:
                note = live.note
            lines.append(_estimate_line(store, item, note=note))

    live_count = sum(1 for line in lines if line.price_source == PriceSource.LIVE)
    estimate_count = len(lines) - live_count
    total = round(sum(line.line_total for line in lines), 2)
    return PriceCheckStoreBasket(
        store=store,
        total=total,
        live_count=live_count,
        estimate_count=estimate_count,
        lines=lines,
        warning=warning,
    )


def filter_comparable_baskets(
    baskets: list[PriceCheckStoreBasket],
) -> tuple[list[PriceCheckStoreBasket], list[PriceCheckSkippedStore]]:
    """Drop stores with zero live matches — never compare invented estimate-only totals."""
    from price_check.models import StoreChain
    from price_check.woolworths_public import online_store

    kept: list[PriceCheckStoreBasket] = []
    skipped: list[PriceCheckSkippedStore] = []
    ww_skip_count = 0
    ww_reason = ""
    for basket in baskets:
        if basket.live_count > 0:
            kept.append(basket)
            continue
        reason = (basket.warning or "").strip() or (
            "No live catalogue prices for this store — not included in comparison."
        )
        if "not included" not in reason.lower():
            reason = f"{reason} Not included in comparison."
        if basket.store.chain == StoreChain.WOOLWORTHS:
            ww_skip_count += 1
            ww_reason = reason
            continue
        skipped.append(PriceCheckSkippedStore(store=basket.store, reason=reason))
    if ww_skip_count:
        # One message for WW — suburb picks were the same online catalogue.
        label = online_store()
        if ww_skip_count > 1:
            reason = (
                "Woolworths live catalogue isn't reachable from this server "
                f"({ww_skip_count} selected). Not included in comparison."
            )
        else:
            reason = ww_reason
        skipped.insert(0, PriceCheckSkippedStore(store=label, reason=reason))
    return kept, skipped


def compute_split(baskets: list[PriceCheckStoreBasket]) -> PriceSplitResult | None:
    if len(baskets) < 2:
        return None
    # Align by ingredient order from first basket
    ingredients = [line.ingredient for line in baskets[0].lines]
    assignments: list[PriceSplitAssignment] = []
    split_total = 0.0
    estimate_count = 0
    live_count = 0

    for idx, ingredient in enumerate(ingredients):
        best: tuple[PriceCheckStoreBasket, PriceCheckLine] | None = None
        for basket in baskets:
            if idx >= len(basket.lines):
                continue
            line = basket.lines[idx]
            if line.ingredient != ingredient:
                # Fall back to name lookup if order drifted
                line = next((l for l in basket.lines if l.ingredient == ingredient), line)
            if best is None or line.line_total < best[1].line_total:
                best = (basket, line)
        if best is None:
            continue
        basket, line = best
        assignments.append(
            PriceSplitAssignment(
                ingredient=ingredient,
                store_id=basket.store.id,
                store_name=basket.store.name,
                chain=basket.store.chain,
                line=line,
            )
        )
        split_total += line.line_total
        if line.price_source == PriceSource.ESTIMATE:
            estimate_count += 1
        else:
            live_count += 1

    cheapest_single = min(b.total for b in baskets)
    split_total = round(split_total, 2)
    savings = round(cheapest_single - split_total, 2)
    note = ""
    if estimate_count:
        note = f"{estimate_count} line(s) use estimates — savings may be approximate."
    return PriceSplitResult(
        total=split_total,
        savings_vs_cheapest_single_store=max(0.0, savings),
        estimate_count=estimate_count,
        live_count=live_count,
        assignments=assignments,
        note=note,
    )


async def run_price_check(
    *,
    stores: list[StoreRef],
    items: list[GroceryLineItem],
    match_fn: MatchFn,
    include_split: bool = False,
) -> PriceCheckResult:
    if not items:
        return PriceCheckResult(baskets=[], split=None)
    # Sequential per store — keeps cloud gateways under timeout and lets one
    # blocked chain (e.g. WW/Akamai) fail fast without starving the others.
    raw: list[PriceCheckStoreBasket] = []
    for store in stores:
        raw.append(await basket_for_store(store, items, match_fn))
    baskets, skipped = filter_comparable_baskets(raw)
    split = compute_split(list(baskets)) if include_split else None
    ordered = sorted(baskets, key=lambda b: (b.total, b.store.name))
    return PriceCheckResult(baskets=ordered, skipped=skipped, split=split)
