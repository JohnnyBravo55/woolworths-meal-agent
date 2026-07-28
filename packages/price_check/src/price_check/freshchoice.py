"""FreshChoice store directory (Myfoodlink). Live search deferred — estimate fallback."""

from __future__ import annotations

from price_check.models import PriceCheckLine, StoreChain, StoreRef

# Stores known to offer Click & Collect / Myfoodlink online shopping.
_FRESHCHOICE_STORES: list[StoreRef] = [
    StoreRef(
        id="freshchoice:barrington",
        chain=StoreChain.FRESHCHOICE,
        name="FreshChoice Barrington",
        address="Barrington, Christchurch",
        suburb="Christchurch",
        pricing_note="Live catalogue not wired yet — estimates used",
    ),
    StoreRef(
        id="freshchoice:christchurch-city",
        chain=StoreChain.FRESHCHOICE,
        name="FreshChoice Christchurch City Market",
        address="Christchurch City",
        suburb="Christchurch",
        pricing_note="Live catalogue not wired yet — estimates used",
    ),
    StoreRef(
        id="freshchoice:cromwell",
        chain=StoreChain.FRESHCHOICE,
        name="FreshChoice Cromwell",
        address="Cromwell",
        suburb="Cromwell",
        pricing_note="Live catalogue not wired yet — estimates used",
    ),
    StoreRef(
        id="freshchoice:parklands",
        chain=StoreChain.FRESHCHOICE,
        name="FreshChoice Parklands",
        address="Parklands, Christchurch",
        suburb="Christchurch",
        pricing_note="Live catalogue not wired yet — estimates used",
    ),
    StoreRef(
        id="freshchoice:nelson-city",
        chain=StoreChain.FRESHCHOICE,
        name="FreshChoice Nelson City",
        address="Nelson",
        suburb="Nelson",
        pricing_note="Live catalogue not wired yet — estimates used",
    ),
]


def list_stores() -> list[StoreRef]:
    return list(_FRESHCHOICE_STORES)


async def match_line(store: StoreRef, ingredient: str, quantity: float, unit: str) -> PriceCheckLine | None:
    """FreshChoice Myfoodlink live search is not implemented yet."""
    _ = (store, ingredient, quantity, unit)
    return None
