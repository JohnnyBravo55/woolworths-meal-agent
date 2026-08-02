# Assisted shop (multi-store) design

**Date:** 2026-08-02  
**Status:** Implemented  
**Related:** Option 2 in NZ multi-store cart options; builds on `2026-07-28-multi-store-price-check-design.md`

## Decision

Users shop at a chosen NZ supermarket branch via a **store-matched checklist + deep links**. The app does **not** write New World / Pak’nSave / FreshChoice carts.

**Woolworths silent cart** stays as an optional accelerator on native (decision A). Assisted shop is available for every chain, including Woolworths.

## Flow

1. Shop list ready → Compare store prices (existing price-check).
2. User expands a store basket → **Shop at [store]** opens the chain shopfront (`store_url`).
3. Per line: **Open** (product URL if known), **Search** (catalogue search URL), **Copy** (product/ingredient name), **Mark bought** (client-only checklist).
4. Fallback: share/export existing CSV/MD when links fail.

## Data

Extend price-check models:

| Field | On | Purpose |
|---|---|---|
| `store_url` | `StoreRef` | Open store homepage / online shop |
| `product_url` | `PriceCheckLine` | Open matched product when SKU/page known |
| `search_url` | `PriceCheckLine` | Open search for ingredient/product name |

Adapters populate URLs (guest/public only). Estimate lines still get `search_url` from store + ingredient.

## Non-goals

- Silent cart for Foodstuffs / FreshChoice
- Browser-extension auto-add
- Persisting mark-bought across sessions
- Replacing Woolworths native add-to-trolley

## UX copy

Prefer “Shop at [store]” / “Open in store site” over “Add to trolley” for assisted paths.
