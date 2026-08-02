# Multi-store price check (design)

**Date:** 2026-07-28  
**Status:** Approved for implementation (local try before push)

## Goal

On the shop list step, users can optionally run a **login-free price check** across ticked **local supermarket branches**, see **per-store totals** (with collapsible per-item breakdown), and optionally a **smart split** that assigns each item to the cheapest ticked store.

## Product decisions

| Decision | Choice |
|---|---|
| Primary mode | Per-store basket totals for the generated shop list |
| Optional mode | Smart split across ticked stores |
| Auth for prices | No store login; Woolworths connect remains cart-only |
| Stores | Woolworths, Pak’nSave, New World, FreshChoice |
| Location | Specific local branches (not chain-only) |
| UX placement | Optional action on shop list (web + mobile) |
| Result UI | Totals + collapsible per-item dropdowns |
| Unmatched items | Keep original shop-list estimated price; mark as estimate on the line |
| Architecture | Live store adapters behind a shared price-check engine (not a national scrape DB) |

## Non-goals (v1)

- Silent add-to-cart for non-Woolworths stores (assisted shop / deep links are in `2026-08-02-assisted-shop-design.md`)
- Replacing Woolworths resolve / budget reconciliation
- National daily scrape warehouse

## Architecture

1. Shop list ingredients (from session `resolved_list`) are the input.
2. User picks local branches → `POST /api/price-check`.
3. Engine queries each store adapter in parallel (guest/public search).
4. Per line: live match or estimate fallback with note.
5. Optional split: cheapest live (or estimate) assignment among ticked stores.
6. Existing Woolworths cart path unchanged.

## APIs

- `GET /api/stores/search?q=&chain=` — branch directory
- `POST /api/price-check` — `{ store_ids, include_split }` using session shop list
- Session remembers last-selected store ids

## FreshChoice note

FreshChoice online uses Myfoodlink (not Foodstuffs Edge). Live prices come from each store’s guest shopfront (`{slug}.store.freshchoice.co.nz/search?q=…`) via HTML product cards — same login-free model as the other chains. If a store/search fails, lines fall back to estimates with an explicit note.

## Error handling

- Adapter/HTTP failure for a store → all lines estimate for that store + store-level warning
- Partial matches OK; summary shows live vs estimate counts
- Split savings annotated when estimates are included
