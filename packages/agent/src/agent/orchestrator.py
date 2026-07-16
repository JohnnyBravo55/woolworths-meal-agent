"""Main orchestrator tying together all agent phases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from agent.budget import BudgetEngine, BudgetSuggestion
from agent.conversation import ConversationManager
from agent.review import ReviewGate
from meal_planner.planner import MealPlanner
from meal_planner.ingredients import build_shopping_ingredients
from shared.models import AgentPhase, ConversationState, GroceryLineItem, MealPlan, ResolvedGroceryList, UserProfile
from woolworths_adapter.cart_merge import merge_line_items_by_sku
from woolworths_adapter.cart_validation import validate_line_item
from woolworths_adapter.client import WoolworthsAdapter, WoolworthsError
from woolworths_adapter.export import export_csv, export_markdown
from woolworths_adapter.resolver import ProductResolver


CartProgressCallback = Callable[[str, GroceryLineItem, str], Awaitable[None] | None]


@dataclass
class CartResult:
    success_count: int = 0
    failure_count: int = 0
    errors: list[str] = field(default_factory=list)
    added_total: float = 0.0
    cart_subtotal: float | None = None
    skipped_offline: int = 0
    session_lost: bool = False
    duplicate_lines_merged: int = 0
    cart_line_count: int | None = None


class MealAgentOrchestrator:
    """Runs the full meal planning → resolution → cart pipeline."""

    def __init__(
        self,
        output_dir: Path | str = "output",
        headless: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.adapter = WoolworthsAdapter(headless=headless)
        self.resolver = ProductResolver(self.adapter)
        self.budget_engine = BudgetEngine(self.adapter, self.resolver)
        self.planner = MealPlanner()
        self.conversation = ConversationManager()
        self.review = ReviewGate()
        self.state = ConversationState()

    async def run_discovery(self, answers: dict) -> UserProfile:
        profile = self.conversation.create_profile_from_answers(answers)
        self.state.profile = profile
        self.state.advance_to(AgentPhase.PLAN_DRAFT)
        return profile

    async def generate_plan(self, profile: UserProfile) -> MealPlan:
        plan = await self.planner.generate(profile)
        self.state.meal_plan = plan
        self.state.advance_to(AgentPhase.PLAN_APPROVAL)
        return plan

    async def generate_plan_from_templates(self, profile: UserProfile) -> MealPlan:
        """Fallback when LLM is unavailable."""
        plan = self.planner._generate_from_templates(profile)
        self.state.meal_plan = plan
        self.state.advance_to(AgentPhase.PLAN_APPROVAL)
        return plan

    def approve_plan(self, approved: bool = True) -> None:
        self.state.plan_approved = approved
        if approved:
            self.state.advance_to(AgentPhase.PRODUCT_RESOLUTION)

    async def resolve_products(self, profile: UserProfile, plan: MealPlan) -> ResolvedGroceryList:
        plan.shared_ingredients = build_shopping_ingredients(plan.meals, profile)
        resolved = await self.resolver.resolve_all(
            plan.shared_ingredients, profile, meal_plan=plan
        )
        self.state.resolved_list = resolved
        self.state.advance_to(AgentPhase.BUDGET_RECONCILIATION)
        return resolved

    async def reconcile_budget(
        self,
        resolved: ResolvedGroceryList,
        profile: UserProfile,
        auto_swap: bool = True,
    ) -> tuple[ResolvedGroceryList, list[BudgetSuggestion]]:
        resolved, suggestions = await self.budget_engine.reconcile(
            resolved, profile, auto_swap=auto_swap
        )
        # Budget trim can drop required meal lines — restore coverage (OFFLINE ok)
        plan = self.state.meal_plan
        if plan is not None:
            from meal_planner.shop_coverage import (
                audit_resolved_shop_coverage,
                heal_resolved_coverage,
            )

            items, heal_issues = heal_resolved_coverage(plan.meals, list(resolved.items), profile)
            coverage = list(resolved.coverage_issues or [])
            for msg in heal_issues:
                if msg not in coverage:
                    coverage.append(msg)
            for msg in audit_resolved_shop_coverage(plan.meals, items, profile):
                if msg not in coverage:
                    coverage.append(msg)
            resolved = self.budget_engine._recalculate(items, profile).model_copy(
                update={
                    "coverage_issues": coverage,
                    "unresolved_ingredients": list(resolved.unresolved_ingredients or []),
                }
            )
        self.state.resolved_list = resolved
        return resolved, suggestions

    def approve_products(self, approved: bool = True) -> None:
        self.state.products_approved = approved
        if approved:
            self.state.advance_to(AgentPhase.CART)

    async def add_to_cart(
        self,
        resolved: ResolvedGroceryList,
        *,
        plan_approved: bool,
        products_approved: bool,
        export_on_failure: bool = True,
        allow_over_budget: bool = False,
        on_progress: CartProgressCallback | None = None,
    ) -> CartResult:
        if not self.review.can_add_to_cart(plan_approved, products_approved):
            raise ValueError("Plan and product list must be approved before cart operations")

        if not resolved.within_budget and not allow_over_budget:
            raise ValueError(
                f"Refusing to add to cart: addable total ${resolved.addable_total:.2f} exceeds "
                f"budget ${resolved.budget_nzd:.2f}. Review the product list or raise your budget."
            )

        self.state.cart_attempted = True
        result = CartResult()

        session_ok = await self.adapter.validate_session()
        if not session_ok:
            result.errors.append(
                "Woolworths session expired or invalid — run: meal-agent login"
            )
            if export_on_failure:
                await self._export_fallback(resolved)
            return result

        addable = resolved.addable_items()
        addable, merged_dupes = merge_line_items_by_sku(addable)
        result.duplicate_lines_merged = merged_dupes
        if merged_dupes:
            result.errors.append(
                f"Merged {merged_dupes} duplicate product(s) — same Woolworths SKU "
                "listed for multiple ingredients"
            )
        offline = resolved.offline_items()
        total_addable = len(addable)

        async def _emit(status: str, item: GroceryLineItem, message: str = "") -> None:
            if on_progress:
                maybe = on_progress(status, item, message)
                if maybe is not None:
                    await maybe

        for item in offline:
            result.skipped_offline += 1
            result.errors.append(
                f"Not added (no Woolworths match): {item.ingredient} — search manually"
            )
            await _emit("skipped", item, "manual search needed")

        for idx, item in enumerate(addable, start=1):
            await _emit("adding", item, f"Adding {idx}/{total_addable}")
            if not item.in_stock:
                result.failure_count += 1
                result.errors.append(f"Skipped out-of-stock: {item.product_name}")
                await _emit("failed", item, "out of stock")
                continue
            profile = self.state.profile
            plan = self.state.meal_plan
            if item.cart_blocked:
                result.failure_count += 1
                msg = item.block_reason or f"Blocked: {item.product_name}"
                result.errors.append(f"{item.ingredient}: {msg}")
                await _emit("failed", item, msg)
                continue
            if profile and item.sku != "OFFLINE":
                v = await validate_line_item(
                    item, profile, adapter=self.adapter, meal_plan=plan
                )
                if v.blocked:
                    result.failure_count += 1
                    msg = v.block_reason or f"Failed validation: {item.product_name}"
                    result.errors.append(f"{item.ingredient}: {msg}")
                    await _emit("failed", item, msg)
                    continue
                for w in v.warnings:
                    if w not in item.warnings:
                        item.warnings.append(w)
                    result.errors.append(f"{item.ingredient}: {w}")
            try:
                await self.adapter.add_to_cart(item.sku, item.quantity, item.unit)
                result.success_count += 1
                result.added_total = round(result.added_total + item.line_total, 2)
                await _emit("success", item, f"Added ${item.line_total:.2f}")
            except WoolworthsError as exc:
                result.failure_count += 1
                result.errors.append(f"{item.ingredient}: {exc}")
                await _emit("failed", item, str(exc))
                if self.adapter.is_auth_failure(exc):
                    result.session_lost = True
                    result.errors.append(
                        "Stopped adding — session lost. Run: meal-agent login, "
                        "then: meal-agent cart-retry --csv <exported list>"
                    )
                    break
            except Exception as exc:
                result.failure_count += 1
                result.errors.append(f"{item.ingredient}: {exc}")

        result.cart_subtotal = await self.adapter.get_cart_subtotal()
        try:
            result.cart_line_count = len(await self.adapter.get_cart_skus())
        except Exception:
            result.cart_line_count = None
        if (
            result.cart_subtotal is not None
            and result.added_total > 0
            and result.cart_subtotal + 5 < result.added_total
        ):
            gap = round(result.added_total - result.cart_subtotal, 2)
            result.errors.append(
                f"Trolley subtotal (${result.cart_subtotal:.2f}) is ${gap:.2f} below "
                f"what we tried to add (${result.added_total:.2f}) — some items may "
                "have failed silently or old trolley items were cleared"
            )

        self.state.cart_success = result.failure_count == 0 and result.success_count > 0
        self.state.cart_errors = result.errors

        if result.failure_count > 0 and export_on_failure:
            await self._export_fallback(resolved)

        self.state.advance_to(AgentPhase.RECIPES)
        return result

    async def _export_fallback(self, resolved: ResolvedGroceryList) -> list[str]:
        md_path = export_markdown(resolved, self.state.meal_plan, self.output_dir)
        csv_path = export_csv(resolved, self.output_dir)
        paths = [str(md_path), str(csv_path)]
        self.state.export_paths = paths
        return paths

    async def export_only(self, resolved: ResolvedGroceryList) -> list[str]:
        """Export shopping list without attempting cart."""
        return await self._export_fallback(resolved)

    async def run_full_pipeline(
        self,
        profile: UserProfile,
        *,
        auto_approve: bool = False,
        export_only: bool = False,
        auto_swap: bool = True,
        offline: bool = False,
    ) -> ConversationState:
        """Run end-to-end pipeline (for demo / scripted runs)."""
        self.state.profile = profile

        if offline or not await self.adapter.is_session_available():
            if offline:
                self.resolver.offline_mode = True

        plan = await self.generate_plan(profile)
        if auto_approve:
            self.approve_plan(True)
        else:
            return self.state

        resolved = await self.resolve_products(profile, plan)
        resolved, _ = await self.reconcile_budget(resolved, profile, auto_swap=auto_swap)

        if auto_approve:
            self.approve_products(True)

        if export_only:
            await self.export_only(resolved)
            self.state.advance_to(AgentPhase.COMPLETE)
            return self.state

        if self.state.products_approved:
            await self.add_to_cart(
                resolved,
                plan_approved=self.state.plan_approved,
                products_approved=self.state.products_approved,
            )

        self.state.advance_to(AgentPhase.COMPLETE)
        return self.state
