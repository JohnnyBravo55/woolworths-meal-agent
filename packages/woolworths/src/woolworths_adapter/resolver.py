"""Map ingredients to Woolworths products with ranking."""

from __future__ import annotations

import asyncio

from shared.allergy import is_product_safe_for_profile, profile_has_gluten_allergy
from shared.gluten_label import GlutenLabelStatus, ProductLabelInfo, assess_gluten_label
from shared.models import (
    BrandPreference,
    GroceryLineItem,
    Ingredient,
    MealPlan,
    ProductMatch,
    ResolvedGroceryList,
    UserProfile,
)
from woolworths_adapter.cart_merge import merge_line_items_by_sku
from woolworths_adapter.cart_validation import audit_resolved_list, validate_product_for_ingredient
from meal_planner.ingredient_normalize import prefers_fresh_produce
from meal_planner.shop_coverage import (
    audit_shop_coverage,
    audit_resolved_shop_coverage,
    format_coverage_issue,
    heal_resolved_coverage,
)
from woolworths_adapter.client import WoolworthsAdapter, WoolworthsError
from woolworths_adapter.quantities import normalize_cart_quantity
from meal_planner.meal_quality import is_leftover_meal, leftover_meal_needs_shop
from woolworths_adapter.search_helpers import is_plausible_match, search_queries_for

# When Woolworths has no exact product, search a close substitute instead of going offline.
_SUBSTITUTE_INGREDIENT: dict[str, str] = {
    "gluten free teriyaki sauce": "gluten free soy sauce",
}

# Search flakes under batch load for these — fetch known NZ stockcodes directly.
_SKU_FALLBACKS: dict[str, tuple[str, ...]] = {
    # Prefer portion packs (cheaper Each) over premium $/kg fillets
    "salmon fillets": ("435067", "916529", "290252", "293302"),
    "salmon fillet": ("435067", "916529", "290252"),
    "salmon": ("435067", "290252"),
    "fish fillets": ("6047258",),
}


def _merge_by_sku(items: list[GroceryLineItem]) -> tuple[list[GroceryLineItem], int]:
    return merge_line_items_by_sku(items)


def _effective_price(match: ProductMatch) -> float:
    return match.sale_price if match.sale_price is not None else match.unit_price


def _brand_score(match: ProductMatch, preference: BrandPreference) -> float:
    brand_lower = match.brand.lower()
    name_lower = match.product_name.lower()
    is_home_brand = any(
        tag in brand_lower or tag in name_lower
        for tag in ("pams", "homebrand", "woolworths", "essentials", "countdown")
    )
    is_premium = any(
        tag in brand_lower or tag in name_lower
        for tag in ("organic", "free range", "angus", "premium", "gold")
    )

    if preference == BrandPreference.BUDGET:
        return 2.0 if is_home_brand else (-1.0 if is_premium else 0.0)
    if preference == BrandPreference.PREMIUM:
        return 2.0 if is_premium else (0.5 if not is_home_brand else -0.5)
    return 1.0 if is_home_brand else (0.5 if not is_premium else 0.0)


def _unit_price_score(match: ProductMatch) -> float:
    price = _effective_price(match)
    if match.cup_price and match.cup_price > 0:
        return -match.cup_price
    return -price


def _freshness_score(ingredient_name: str, product_name: str) -> float:
    """Prefer fresh produce over frozen when the recipe calls for fresh veg."""
    if not prefers_fresh_produce(ingredient_name):
        return 0.0
    name = product_name.lower()
    if "frozen" in name:
        return -3.0
    if any(x in name for x in ("fresh", " each", "head", "loose", "bunch")):
        return 0.5
    return 0.0


def _packaging_penalty(ingredient_name: str, product_name: str) -> float:
    """Prefer minimal packaging — blocks over snack portions."""
    ing = ingredient_name.lower()
    name = product_name.lower()
    if "cheese" in ing and "cream" not in ing:
        if any(x in name for x in ("stick", "sticks", "snack", "squeezy", "string")):
            return -5.0
        if "block" in name:
            return 1.0
    if "cracker" in ing or ing == "crispbread":
        if "rice cracker" in name or "rice cake" in name:
            return 0.5
    return 0.0


def rank_products(
    matches: list[ProductMatch],
    preference: BrandPreference,
    ingredient_name: str = "",
    profile: UserProfile | None = None,
) -> list[ProductMatch]:
    """Rank products by brand preference and unit price (prefer in-stock)."""

    def _filter(pool: list[ProductMatch]) -> list[ProductMatch]:
        out = [m for m in pool if m.sku]
        if ingredient_name:
            out = [
                m
                for m in out
                if is_plausible_match(ingredient_name, m.product_name, m.brand)
            ]
        if profile:
            out = [
                m
                for m in out
                if is_product_safe_for_profile(
                    m.product_name, m.brand, profile, ingredient_name=ingredient_name
                )
            ]
        return out

    in_stock = _filter([m for m in matches if m.in_stock])
    # Fall back to out-of-stock matches — better than silent OFFLINE estimates
    candidates = in_stock or _filter(list(matches))
    if not candidates:
        return []

    ing = ingredient_name.lower()
    prefer_cheap_protein = any(x in ing for x in ("salmon", "fish fillet", "white fish"))

    def score(match: ProductMatch) -> tuple[float, float, float, float, float]:
        price_score = _unit_price_score(match)
        if prefer_cheap_protein:
            # Don't let home-brand premium $/kg beat affordable portion packs
            return (
                1.0 if match.in_stock else 0.0,
                price_score,
                _freshness_score(ingredient_name, match.product_name),
                _brand_score(match, preference),
                _packaging_penalty(ingredient_name, match.product_name),
            )
        return (
            1.0 if match.in_stock else 0.0,
            _brand_score(match, preference),
            _freshness_score(ingredient_name, match.product_name),
            _packaging_penalty(ingredient_name, match.product_name),
            price_score,
        )

    return sorted(candidates, key=score, reverse=True)


class ProductResolver:
    """Resolve ingredients to Woolworths SKUs with live pricing."""

    def __init__(self, adapter: WoolworthsAdapter | None = None, offline_mode: bool = False):
        self.adapter = adapter or WoolworthsAdapter()
        self.offline_mode = offline_mode

    def _offline_line(self, ingredient: Ingredient, profile: UserProfile) -> GroceryLineItem:
        from woolworths_adapter.estimates import estimate_price

        unit_price = estimate_price(ingredient.name)
        # Fake product for normalization — offline always buys by Each
        fake = ProductMatch(sku="OFFLINE", product_name=ingredient.name, unit_price=unit_price)
        quantity, unit = normalize_cart_quantity(ingredient, fake, household_size=profile.household_size)
        return GroceryLineItem(
            ingredient=ingredient.name,
            sku="OFFLINE",
            product_name=f"{ingredient.name.title()} (estimated)",
            quantity=quantity,
            unit=unit if unit in ("Each", "Kilogram") else "Each",
            unit_price=unit_price,
            line_total=round(unit_price * quantity, 2),
            for_meals=ingredient.for_meals,
            in_stock=True,
            is_mandatory=ingredient.is_mandatory,
            product_url="",
        )

    async def _search_matches(
        self,
        ingredient: Ingredient,
        profile: UserProfile,
        *,
        expanded: bool = False,
    ) -> list[ProductMatch]:
        """Try multiple search queries and merge plausible results."""
        from meal_planner.ingredient_normalize import fruit_fallback_queries, is_fruit_ingredient

        all_matches: list[ProductMatch] = []
        seen_skus: set[str] = set()

        query_lists = [
            search_queries_for(
                ingredient.name,
                profile,
                profile.chef_id,
                expanded=expanded,
            )
        ]
        if is_fruit_ingredient(ingredient.name):
            query_lists.append(fruit_fallback_queries())

        for queries in query_lists:
            for query in queries:
                results: list[ProductMatch] = []
                for attempt in range(2):
                    try:
                        results = await self.adapter.search(query, limit=8)
                        break
                    except WoolworthsError:
                        if attempt == 0:
                            await asyncio.sleep(0.4)
                            continue
                        results = []
                for match in results:
                    if match.sku in seen_skus:
                        continue
                    if not is_plausible_match(ingredient.name, match.product_name, match.brand):
                        continue
                    if not is_product_safe_for_profile(
                        match.product_name, match.brand, profile, ingredient_name=ingredient.name
                    ):
                        continue
                    seen_skus.add(match.sku)
                    all_matches.append(match)

        return rank_products(
            all_matches, profile.brand_preference, ingredient.name, profile=profile
        )

    async def _select_match_for_profile(
        self,
        ranked: list[ProductMatch],
        ingredient: Ingredient,
        profile: UserProfile,
    ) -> tuple[ProductMatch | None, list[str]]:
        if not ranked:
            return None, []

        if not profile_has_gluten_allergy(profile):
            return ranked[0], []

        best_safe: ProductMatch | None = None
        best_traces: ProductMatch | None = None
        best_unknown: ProductMatch | None = None
        trace_warning: list[str] = []
        unknown_warning: list[str] = []

        candidates = ranked[:6]
        labels = await asyncio.gather(
            *(self.adapter.get_product_label(match.sku) for match in candidates)
        )

        for match, label_info in zip(candidates, labels, strict=True):
            assessment = assess_gluten_label(label_info or ProductLabelInfo())
            fit = validate_product_for_ingredient(
                ingredient.name,
                match.product_name,
                match.brand,
                profile=profile,
                label_assessment=assessment,
            )
            if fit.blocked:
                continue
            if not is_product_safe_for_profile(
                match.product_name,
                match.brand,
                profile,
                ingredient_name=ingredient.name,
                label_assessment=assessment,
            ):
                continue
            if assessment.status == GlutenLabelStatus.CONTAINS:
                continue
            if assessment.status == GlutenLabelStatus.SAFE and best_safe is None:
                best_safe = match
            elif assessment.status == GlutenLabelStatus.TRACES and best_traces is None:
                best_traces = match
                trace_warning = [assessment.user_warning or "May contain traces of gluten"]
            elif assessment.status == GlutenLabelStatus.UNKNOWN and best_unknown is None:
                best_unknown = match
                unknown_warning = [
                    assessment.user_warning or "Could not verify ingredients — check packaging"
                ]

        if best_safe:
            return best_safe, []
        if best_traces:
            return best_traces, trace_warning
        if best_unknown:
            return best_unknown, unknown_warning
        return None, []

    @staticmethod
    def _should_skip_search(ingredient: Ingredient, meal_plan: MealPlan | None) -> bool:
        """Skip Woolworths search for leftover-meal ingredients (already cooked)."""
        if not meal_plan:
            return False
        leftover_names = {m.name for m in meal_plan.meals if is_leftover_meal(m)}
        linked = [m for m in ingredient.for_meals if m not in ("mandatory",)]
        if linked and all(m in leftover_names for m in linked):
            return not leftover_meal_needs_shop(ingredient.name)
        return False

    async def resolve_ingredient(
        self,
        ingredient: Ingredient,
        profile: UserProfile,
        *,
        meal_plan: MealPlan | None = None,
    ) -> GroceryLineItem | None:
        from meal_planner.pantry import is_in_pantry

        if is_in_pantry(ingredient.name, profile.pantry_items):
            return None

        if self._should_skip_search(ingredient, meal_plan):
            return None

        search_ingredient = ingredient
        if profile_has_gluten_allergy(profile):
            lower = ingredient.name.lower()
            if "bread" in lower and "gluten" not in lower:
                search_ingredient = ingredient.model_copy(update={"name": "gluten free bread"})
            elif lower in ("crackers", "cracker", "crispbread"):
                search_ingredient = ingredient.model_copy(update={"name": "crackers"})
            elif "taco shell" in lower and "gluten" not in lower:
                search_ingredient = ingredient.model_copy(update={"name": "taco shells"})

        if self.offline_mode:
            return self._offline_line(search_ingredient, profile)

        search_attempts: list[tuple[Ingredient, bool]] = [
            (search_ingredient, False),
            (search_ingredient, True),
        ]
        sub_name = _SUBSTITUTE_INGREDIENT.get(search_ingredient.name.lower())
        if sub_name:
            sub_ing = search_ingredient.model_copy(update={"name": sub_name})
            search_attempts.extend([(sub_ing, False), (sub_ing, True)])

        for round_idx in range(3):
            if round_idx > 0:
                # Back off then retry — Woolworths search flakes under batch load
                await asyncio.sleep(0.5 * (round_idx + 1))
            for attempt_ing, expanded in search_attempts:
                ranked = await self._search_matches(attempt_ing, profile, expanded=expanded)
                if not ranked:
                    continue
                best, warnings = await self._select_match_for_profile(
                    ranked, ingredient, profile
                )
                if best:
                    return self._line_from_match(
                        ingredient, attempt_ing, best, profile, warnings
                    )

        # Last resort: known stockcodes (salmon search is especially flaky)
        fallback = await self._resolve_via_sku_fallback(search_ingredient, profile)
        if fallback:
            return fallback

        return self._offline_line(search_ingredient, profile)

    def _line_from_match(
        self,
        ingredient: Ingredient,
        attempt_ing: Ingredient,
        best: ProductMatch,
        profile: UserProfile,
        warnings: list[str],
    ) -> GroceryLineItem:
        unit_price = _effective_price(best)
        quantity, cart_unit = normalize_cart_quantity(
            attempt_ing, best, household_size=profile.household_size
        )
        return GroceryLineItem(
            ingredient=ingredient.name,
            sku=best.sku,
            product_name=best.product_name,
            quantity=quantity,
            unit=cart_unit,
            unit_price=unit_price,
            line_total=round(unit_price * quantity, 2),
            for_meals=ingredient.for_meals,
            in_stock=best.in_stock,
            is_mandatory=ingredient.is_mandatory,
            product_url=self.adapter.product_url(best.sku, best.product_name),
            warnings=warnings,
        )

    async def _resolve_via_sku_fallback(
        self,
        ingredient: Ingredient,
        profile: UserProfile,
    ) -> GroceryLineItem | None:
        skus = _SKU_FALLBACKS.get(ingredient.name.lower())
        if not skus:
            return None
        for sku in skus:
            try:
                match = await self.adapter.get_product_match(sku)
            except Exception:
                match = None
            if not match:
                continue
            if not is_plausible_match(ingredient.name, match.product_name, match.brand):
                continue
            if not is_product_safe_for_profile(
                match.product_name, match.brand, profile, ingredient_name=ingredient.name
            ):
                continue
            best, warnings = await self._select_match_for_profile([match], ingredient, profile)
            if best:
                return self._line_from_match(ingredient, ingredient, best, profile, warnings)
        return None

    async def resolve_all(
        self,
        ingredients: list[Ingredient],
        profile: UserProfile,
        *,
        meal_plan: MealPlan | None = None,
    ) -> ResolvedGroceryList:
        items: list[GroceryLineItem] = []
        unresolved: list[str] = []

        mandatory = [i for i in ingredients if i.is_mandatory]
        meal_items = [i for i in ingredients if not i.is_mandatory]

        for ingredient in mandatory + meal_items:
            line = await self.resolve_ingredient(
                ingredient, profile, meal_plan=meal_plan
            )
            if line:
                items.append(line)
            else:
                unresolved.append(ingredient.name)

        # Collapse duplicate ingredient lines (e.g. broccoli listed twice)
        by_ingredient: dict[str, GroceryLineItem] = {}
        for line in items:
            key = line.ingredient.lower()
            if key not in by_ingredient:
                by_ingredient[key] = line
                continue
            existing = by_ingredient[key]
            if line.sku != "OFFLINE" and existing.sku == "OFFLINE":
                by_ingredient[key] = line
            elif line.sku != "OFFLINE" and existing.sku == line.sku:
                existing.quantity = max(existing.quantity, line.quantity)
                existing.line_total = round(existing.unit_price * existing.quantity, 2)
                for meal in line.for_meals:
                    if meal not in existing.for_meals:
                        existing.for_meals.append(meal)
        items = list(by_ingredient.values())

        items, _ = _merge_by_sku(items)

        items = await audit_resolved_list(
            items, profile, adapter=self.adapter, meal_plan=meal_plan
        )

        coverage_issues: list[str] = []
        if meal_plan:
            items, heal_issues = heal_resolved_coverage(meal_plan.meals, items, profile)
            # Validate any newly added Manual rows
            items = await audit_resolved_list(
                items, profile, adapter=None, meal_plan=meal_plan
            )
            coverage_issues.extend(heal_issues)
            for issue in audit_shop_coverage(meal_plan.meals, ingredients, profile):
                msg = format_coverage_issue(issue)
                if msg not in coverage_issues:
                    coverage_issues.append(msg)
            for message in audit_resolved_shop_coverage(meal_plan.meals, items, profile):
                if message not in coverage_issues:
                    coverage_issues.append(message)

        # Drop unresolved entries that heal restored onto the list
        on_list = {i.ingredient.lower() for i in items}
        unresolved = [u for u in unresolved if u.lower() not in on_list]

        mandatory_subtotal = sum(i.line_total for i in items if i.is_mandatory)
        meal_subtotal = sum(i.line_total for i in items if not i.is_mandatory)
        total = round(mandatory_subtotal + meal_subtotal, 2)

        return ResolvedGroceryList(
            items=items,
            mandatory_subtotal=round(mandatory_subtotal, 2),
            meal_subtotal=round(meal_subtotal, 2),
            total=total,
            budget_nzd=profile.budget_nzd,
            within_budget=round(sum(i.line_total for i in items if i.sku != "OFFLINE"), 2)
            <= profile.budget_nzd,
            unresolved_ingredients=unresolved,
            coverage_issues=coverage_issues,
        )
