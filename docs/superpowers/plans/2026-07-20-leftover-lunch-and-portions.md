# Implementation plan: leftover lunch + portions + day order

## Files

- `packages/meal_planner/src/meal_planner/chefs.py` — shared leftover lunch rules in `_NZ_BASE`
- `packages/meal_planner/src/meal_planner/planner.py` — practical lunch prompt + fallback templates
- `packages/meal_planner/src/meal_planner/meal_quality.py` — fix `scale_dinner_portions_for_leftovers`
- `apps/mobile/app/recipes.tsx` — Mon–Sun day sort
- `apps/web/src/steps/RecipesStep.tsx` — Mon–Sun day sort
- `tests/test_meal_quality.py` — scaling tests

## Tasks

1. Update prompts/templates for leftover timing + format fit
2. Fix portion scaler (1.5× weight only, next-day leftover dinners only, skip packs/blocks)
3. Sort recipes by weekday order
4. Pytest for scaler; commit and push
