"""Models for multi-store price check."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class StoreChain(str, Enum):
    WOOLWORTHS = "woolworths"
    PAKNSAVE = "paknsave"
    NEW_WORLD = "new_world"
    FRESHCHOICE = "freshchoice"


class PriceSource(str, Enum):
    LIVE = "live"
    ESTIMATE = "estimate"


class StoreRef(BaseModel):
    id: str
    chain: StoreChain
    name: str
    address: str = ""
    suburb: str = ""
    latitude: float | None = None
    longitude: float | None = None
    pricing_note: str = ""


class PriceCheckLine(BaseModel):
    ingredient: str
    quantity: float = 1.0
    unit: str = "each"
    product_name: str = ""
    sku: str = ""
    unit_price: float
    line_total: float
    price_source: PriceSource = PriceSource.ESTIMATE
    note: str = ""


class PriceCheckStoreBasket(BaseModel):
    store: StoreRef
    total: float
    live_count: int = 0
    estimate_count: int = 0
    lines: list[PriceCheckLine] = Field(default_factory=list)
    warning: str = ""


class PriceSplitAssignment(BaseModel):
    ingredient: str
    store_id: str
    store_name: str
    chain: StoreChain
    line: PriceCheckLine


class PriceSplitResult(BaseModel):
    total: float
    savings_vs_cheapest_single_store: float
    estimate_count: int = 0
    live_count: int = 0
    assignments: list[PriceSplitAssignment] = Field(default_factory=list)
    note: str = ""


class PriceCheckRequest(BaseModel):
    store_ids: list[str]
    include_split: bool = False


class PriceCheckResult(BaseModel):
    baskets: list[PriceCheckStoreBasket] = Field(default_factory=list)
    split: PriceSplitResult | None = None
