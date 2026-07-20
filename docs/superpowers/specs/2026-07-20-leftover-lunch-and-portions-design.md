# Leftover lunch rules, recipe day order, and portion scaling

**Date:** 2026-07-20  
**Status:** Approved for implementation

## Goals

1. Practical lunches never reuse **same-day** dinner (lunch comes before dinner).
2. Day-1 lunch is a simple **original** meal; leftovers only from day N dinner → day N+1 lunch.
3. Chefs match leftover form to lunch format (no curry wraps/sandwiches).
4. Recipes UI lists days **Monday → Sunday**.
5. Dinner portion scaling for leftovers is modest and correct — not × household size on packs/blocks.

## Decisions

| Topic | Choice |
|-------|--------|
| Day-1 lunch | Simple original (own protein/carb/veg) |
| Leftover timing | Previous dinner → next lunch only |
| Curry/stew/soup leftovers | Reheat with rice (extra or leftover rice), never wraps/sandwiches |
| Wrap/sandwich leftovers | Firm items only (roast/grill, patties, salad-friendly strips) |
| Portion scale | ~1.5× weight protein/carb on dinners that feed a next-day leftover lunch |
| Pack/block items | Do not auto-scale (taco packs, cheese blocks, wrap packs) |
| Recipes day order | Explicit Mon–Sun sort in mobile + web recipes views |

## Out of scope

- Hard schema linking lunch → source dinner day
- Post-plan LLM regenerator for leftover format mismatches
- Shop resolver quantity logic beyond dinner ingredient scaling
