"""Budget reconciliation with mandatory-items-first allocation."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models import BudgetMode, GroceryLineItem, ProductMatch, ResolvedGroceryList, UserProfile
from woolworths_adapter.client import WoolworthsAdapter
from woolworths_adapter.cart_validation import validate_product_for_ingredient
from woolworths_adapter.resolver import ProductResolver, rank_products
from woolworths_adapter.search_helpers import is_plausible_match


@dataclass
class BudgetSuggestion:
    action: str
    ingredient: str
    current_sku: str
    suggested_sku: str | None
    savings: float
    message: str


def _normalize_product_label(name: str) -> str:
    return " ".join(name.lower().split())


def _swap_line_total(item: GroceryLineItem, candidate: ProductMatch) -> float | None:
    """New line total for a substitute — only when cart units match."""
    if candidate.unit != item.unit:
        return None
    price = candidate.sale_price if candidate.sale_price is not None else candidate.unit_price
    if price <= 0 or item.unit_price <= 0:
        return None
    return round(price * item.quantity, 2)


def _valid_swap_savings(item: GroceryLineItem, candidate: ProductMatch) -> float | None:
    """Savings from swapping to a cheaper product with the same cart unit."""
    if candidate.unit != item.unit:
        return None
    new_total = _swap_line_total(item, candidate)
    if new_total is None:
        return None
    if new_total >= item.line_total:
        return None
    savings = round(item.line_total - new_total, 2)
    if savings < 0.5:
        return None
    return savings


class BudgetEngine:
    """Reconcile grocery list against budget with swap suggestions."""

    WASTE_SLACK = 0.05

    def __init__(
        self,
        adapter: WoolworthsAdapter | None = None,
        resolver: ProductResolver | None = None,
    ):
        self.adapter = adapter or WoolworthsAdapter()
        self.resolver = resolver or ProductResolver(self.adapter)

    def effective_budget(self, profile: UserProfile) -> float:
        slack = profile.budget_nzd * self.WASTE_SLACK
        return profile.budget_nzd - slack

    def summarize(self, resolved: ResolvedGroceryList) -> str:
        lines = [
            f"Mandatory items: ${resolved.mandatory_subtotal:.2f}",
            f"Meal ingredients: ${resolved.meal_subtotal:.2f}",
            f"Total: ${resolved.total:.2f} / ${resolved.budget_nzd:.2f}",
        ]
        if resolved.within_budget:
            lines.append("Status: Within budget")
        else:
            over = resolved.total - resolved.budget_nzd
            lines.append(f"Status: Over budget by ${over:.2f}")
        return "\n".join(lines)

    async def suggest_swaps(
        self,
        resolved: ResolvedGroceryList,
        profile: UserProfile,
    ) -> list[BudgetSuggestion]:
        """Find cheaper alternatives for non-mandatory items."""
        suggestions: list[BudgetSuggestion] = []
        if resolved.within_budget:
            return suggestions

        for item in resolved.items:
            if item.is_mandatory or item.sku == "OFFLINE":
                continue

            try:
                matches = await self.adapter.search(item.ingredient, limit=10)
            except Exception:
                continue

            ranked = rank_products(
                matches, profile.brand_preference, item.ingredient, profile=profile
            )
            current_label = _normalize_product_label(item.product_name)
            for candidate in ranked:
                if candidate.sku == item.sku:
                    continue
                if not is_plausible_match(item.ingredient, candidate.product_name, candidate.brand):
                    continue
                swap_check = validate_product_for_ingredient(
                    item.ingredient, candidate.product_name, candidate.brand
                )
                if swap_check.blocked:
                    continue
                if _normalize_product_label(candidate.product_name) == current_label:
                    continue

                candidate_total = _swap_line_total(item, candidate)
                if candidate_total is None:
                    continue
                savings = _valid_swap_savings(item, candidate)
                if savings is None:
                    continue

                suggestions.append(
                    BudgetSuggestion(
                        action="swap",
                        ingredient=item.ingredient,
                        current_sku=item.sku,
                        suggested_sku=candidate.sku,
                        savings=savings,
                        message=(
                            f"{item.product_name} ${item.line_total:.2f} → "
                            f"{candidate.product_name} ${candidate_total:.2f}"
                        ),
                    )
                )
                break

        return sorted(suggestions, key=lambda s: s.savings, reverse=True)

    async def apply_swaps(
        self,
        resolved: ResolvedGroceryList,
        suggestions: list[BudgetSuggestion],
        profile: UserProfile,
        max_swaps: int = 10,
    ) -> ResolvedGroceryList:
        """Apply top swap suggestions until within budget or max swaps reached."""
        items = list(resolved.items)
        applied = 0
        # When far over budget, allow more swaps
        over = resolved.total - profile.budget_nzd
        if over > 40:
            max_swaps = max(max_swaps, 14)

        for suggestion in suggestions:
            if applied >= max_swaps:
                break
            if resolved.within_budget:
                break
            if not suggestion.suggested_sku:
                continue

            for idx, item in enumerate(items):
                if item.sku != suggestion.current_sku:
                    continue

                try:
                    matches = await self.adapter.search(item.ingredient, limit=10)
                except Exception:
                    break

                replacement = next(
                    (m for m in matches if m.sku == suggestion.suggested_sku),
                    None,
                )
                if not replacement:
                    break

                unit_price = replacement.sale_price or replacement.unit_price
                new_total = _swap_line_total(item, replacement)
                if new_total is None:
                    break
                items[idx] = GroceryLineItem(
                    ingredient=item.ingredient,
                    sku=replacement.sku,
                    product_name=replacement.product_name,
                    quantity=item.quantity,
                    unit=replacement.unit if replacement.unit in ("Each", "Kilogram") else item.unit,
                    unit_price=unit_price,
                    line_total=new_total,
                    for_meals=item.for_meals,
                    in_stock=replacement.in_stock,
                    is_mandatory=item.is_mandatory,
                    product_url=self.adapter.product_url(replacement.sku, replacement.product_name),
                )
                applied += 1
                break

            resolved = self._recalculate(items, profile)
            if profile.budget_mode == BudgetMode.HARD and resolved.within_budget:
                break

        return resolved

    def _recalculate(
        self,
        items: list[GroceryLineItem],
        profile: UserProfile,
    ) -> ResolvedGroceryList:
        mandatory_subtotal = sum(i.line_total for i in items if i.is_mandatory)
        meal_subtotal = sum(i.line_total for i in items if not i.is_mandatory)
        total = round(mandatory_subtotal + meal_subtotal, 2)

        return ResolvedGroceryList(
            items=items,
            mandatory_subtotal=round(mandatory_subtotal, 2),
            meal_subtotal=round(meal_subtotal, 2),
            total=total,
            budget_nzd=profile.budget_nzd,
            within_budget=total <= self.effective_budget(profile),
            unresolved_ingredients=[],
        )

    async def reconcile(
        self,
        resolved: ResolvedGroceryList,
        profile: UserProfile,
        auto_swap: bool = True,
    ) -> tuple[ResolvedGroceryList, list[BudgetSuggestion]]:
        """Run budget check and optionally apply swaps or trim items."""
        suggestions: list[BudgetSuggestion] = []
        if resolved.within_budget:
            return resolved, suggestions

        suggestions = await self.suggest_swaps(resolved, profile)
        if auto_swap and profile.budget_mode == BudgetMode.HARD and suggestions:
            resolved = await self.apply_swaps(resolved, suggestions, profile)

        if not resolved.within_budget and profile.budget_mode == BudgetMode.HARD:
            resolved = self.trim_to_budget(resolved, profile)

        return resolved, suggestions

    @staticmethod
    def _is_core_protein_line(item) -> bool:
        """Meal-defining proteins — trimming these creates OFFLINE heal holes."""
        name = (getattr(item, "ingredient", "") or "").lower()
        return any(
            p in name
            for p in (
                "salmon",
                "chicken",
                "beef",
                "pork",
                "lamb",
                "fish fillet",
                "mince",
                "tofu",
                "prawn",
            )
        )

    def trim_to_budget(
        self,
        resolved: ResolvedGroceryList,
        profile: UserProfile,
    ) -> ResolvedGroceryList:
        """Remove non-mandatory items (most expensive first) until within budget."""
        items = list(resolved.items)
        cap = self.effective_budget(profile)

        while items and sum(i.line_total for i in items) > cap:
            optional = [
                i
                for i in items
                if not i.is_mandatory and not self._is_core_protein_line(i)
            ]
            if not optional:
                break
            optional.sort(key=lambda i: i.line_total, reverse=True)
            items.remove(optional[0])

        return self._recalculate(items, profile)
