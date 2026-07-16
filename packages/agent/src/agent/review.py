"""Human approval gates before cart operations."""

from __future__ import annotations

from shared.models import MealPlan, MealSlot, ResolvedGroceryList, UserProfile


class ReviewGate:
    """Enforces human confirmation before cart writes."""

    @staticmethod
    def format_meal_plan_summary(plan: MealPlan) -> str:
        lines = ["=== MEAL PLAN ===", ""]
        if plan.chef_notes:
            lines.append(f"Chef notes: {plan.chef_notes}")
            lines.append("")

        for meal in plan.meals:
            lines.append(f"{meal.day_label} [{meal.slot.value}]: {meal.name}")
            lines.append(f"  {meal.description} (~{meal.prep_time_minutes} min)")
            lines.append("")

        lines.append(f"Shopping list: {len(plan.shared_ingredients)} unique ingredients")
        return "\n".join(lines)

    @staticmethod
    def format_product_list(resolved: ResolvedGroceryList) -> str:
        lines = [
            "=== PRODUCT LIST ===",
            f"List total (incl. estimates): ${resolved.total:.2f}",
            f"Will add to cart (live SKUs): ${resolved.addable_total:.2f} ({len(resolved.addable_items())} items)",
            f"Manual search needed: ${resolved.offline_total:.2f} ({len(resolved.offline_items())} items)",
            f"Budget: ${resolved.budget_nzd:.2f}",
            "",
        ]
        for item in resolved.items:
            tag = " [MANDATORY]" if item.is_mandatory else ""
            offline = " [MANUAL — no SKU found]" if item.sku == "OFFLINE" else ""
            stock = "" if item.in_stock else " [OUT OF STOCK]"
            lines.append(
                f"• {item.ingredient}{tag}{offline}: {item.product_name} "
                f"× {item.quantity} {item.unit} = ${item.line_total:.2f}{stock}"
            )
            if item.sku != "OFFLINE":
                lines.append(f"  SKU: {item.sku}")

        if resolved.unresolved_ingredients:
            lines.append("")
            lines.append("Unresolved (manual search needed):")
            for name in resolved.unresolved_ingredients:
                lines.append(f"  - {name}")

        if resolved.coverage_issues:
            lines.append("")
            lines.append("Recipe coverage gaps:")
            for issue in resolved.coverage_issues:
                lines.append(f"  - {issue}")

        return "\n".join(lines)

    @staticmethod
    def format_allergy_confirmation(profile: UserProfile) -> str:
        if not profile.allergies:
            return ""
        return (
            "\n⚠ ALLERGY CONFIRMATION\n"
            f"The following allergens will be excluded: {', '.join(profile.allergies)}\n"
            "Please verify this is correct before proceeding.\n"
        )

    @staticmethod
    def format_recipes(plan: MealPlan, *, slot: MealSlot | None = None) -> str:
        meals = plan.meals if slot is None else [m for m in plan.meals if m.slot == slot]
        title = "=== RECIPES ===" if slot is None else f"=== {slot.value.upper()} RECIPES ==="
        lines = [title, ""]
        for meal in meals:
            lines.append(f"## {meal.name} ({meal.day_label})")
            lines.append(meal.description)
            lines.append("")
            lines.append("Ingredients:")
            for ing in meal.ingredients:
                lines.append(f"  - {ing.quantity} {ing.unit} {ing.name}")
            lines.append("")
            lines.append("Steps:")
            for i, step in enumerate(meal.steps, 1):
                lines.append(f"  {i}. {step}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def format_dinner_recipes(plan: MealPlan) -> str:
        return ReviewGate.format_recipes(plan, slot=MealSlot.DINNER)

    @staticmethod
    def can_add_to_cart(plan_approved: bool, products_approved: bool) -> bool:
        return plan_approved and products_approved

    @staticmethod
    def cart_disclaimer() -> str:
        return (
            "This agent will add items to your Woolworths cart only. "
            "It will NEVER complete checkout. You review and pay on woolworths.co.nz."
        )
