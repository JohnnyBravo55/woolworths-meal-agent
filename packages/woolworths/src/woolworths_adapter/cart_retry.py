"""Retry cart adds from an exported shopping list CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from woolworths_adapter.client import WoolworthsAdapter, WoolworthsError


@dataclass
class CartRetryResult:
    success_count: int = 0
    failure_count: int = 0
    skipped_in_cart: int = 0
    skipped_offline: int = 0
    added_total: float = 0.0
    cart_subtotal: float | None = None
    errors: list[str] = field(default_factory=list)


def load_csv_items(path: Path | str) -> list[dict[str, str]]:
    """Load addable rows from a shopping list export CSV."""
    rows: list[dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sku = (row.get("sku") or "").strip()
            if not sku or sku.upper() == "OFFLINE":
                continue
            rows.append(row)
    return rows


async def retry_cart_from_csv(
    csv_path: Path | str,
    *,
    adapter: WoolworthsAdapter | None = None,
    missing_only: bool = True,
) -> CartRetryResult:
    """Add items from a shopping list CSV. By default skips SKUs already in the trolley."""
    adapter = adapter or WoolworthsAdapter()
    result = CartRetryResult()
    path = Path(csv_path)

    if not path.exists():
        raise FileNotFoundError(f"Shopping list not found: {path}")

    if not await adapter.validate_session():
        result.errors.append(
            "Woolworths session expired or invalid — run: meal-agent login"
        )
        return result

    items = load_csv_items(path)
    cart_skus: set[str] = set()
    if missing_only:
        try:
            cart_skus = await adapter.get_cart_skus()
        except WoolworthsError as exc:
            result.errors.append(f"Could not read trolley: {exc}")

    for row in items:
        sku = row["sku"]
        ingredient = row.get("ingredient", sku)
        if missing_only and sku in cart_skus:
            result.skipped_in_cart += 1
            continue

        quantity = float(row.get("quantity") or 1)
        unit = row.get("unit") or "Each"
        line_total = float(row.get("line_total") or 0)

        try:
            await adapter.add_to_cart(sku, quantity, unit)
            result.success_count += 1
            result.added_total = round(result.added_total + line_total, 2)
            cart_skus.add(sku)
        except WoolworthsError as exc:
            result.failure_count += 1
            result.errors.append(f"{ingredient}: {exc}")
            if adapter.is_auth_failure(exc):
                result.errors.append(
                    "Session lost mid-retry — run: meal-agent login, then retry again"
                )
                break

    result.cart_subtotal = await adapter.get_cart_subtotal()
    return result
