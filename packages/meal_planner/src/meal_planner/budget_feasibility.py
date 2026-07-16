"""Estimate whether requested meal counts fit the grocery budget."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models import LunchMode, UserProfile

# Rough NZ Woolworths cost per meal (ingredients only, per household batch)
_COST_PER_MEAL_NZD = {
    "dinner": 22.0,
    "lunch_original": 10.0,
    "lunch_practical": 4.0,
    "snack": 5.0,
    "breakfast": 6.0,
}


@dataclass
class BudgetFeasibility:
    feasible: bool
    estimated_total: float
    budget_nzd: float
    message: str
    suggested_budget_nzd: float | None = None
    suggested_meals: dict[str, int] | None = None


def estimate_plan_cost(profile: UserProfile) -> float:
    mr = profile.meals_requested
    lunch_key = "lunch_practical" if profile.lunch_mode == LunchMode.PRACTICAL else "lunch_original"
    scale = max(1.0, profile.household_size / 2.0)
    total = (
        mr.dinner * _COST_PER_MEAL_NZD["dinner"]
        + mr.lunch * _COST_PER_MEAL_NZD[lunch_key]
        + mr.snacks * _COST_PER_MEAL_NZD["snack"]
        + mr.breakfast * _COST_PER_MEAL_NZD["breakfast"]
    )
    return round(total * scale, 2)


def check_budget_feasibility(profile: UserProfile) -> BudgetFeasibility:
    """Warn when meal count likely exceeds budget before planning."""
    estimated = estimate_plan_cost(profile)
    budget = profile.budget_nzd
    mr = profile.meals_requested

    if estimated <= budget * 0.95:
        return BudgetFeasibility(
            feasible=True,
            estimated_total=estimated,
            budget_nzd=budget,
            message="",
        )

    # Suggest proportional meal reduction (keep dinners, trim lunches/snacks)
    ratio = (budget * 0.9) / estimated if estimated > 0 else 1.0
    suggested_lunch = max(0, int(mr.lunch * ratio))
    suggested_snack = max(0, int(mr.snacks * ratio))
    suggested_dinner = max(1, int(mr.dinner * ratio)) if mr.dinner > 0 else 0

    suggested_budget = round(budget * (estimated / (budget * 0.9)), 0) if budget > 0 else estimated

    return BudgetFeasibility(
        feasible=False,
        estimated_total=estimated,
        budget_nzd=budget,
        message=(
            f"About {mr.total_meals()} meals may cost ~${estimated:.0f} on ingredients — "
            f"above your ${budget:.0f} budget. "
            f"Try fewer lunches/snacks (e.g. {suggested_dinner} dinners, {suggested_lunch} lunches, "
            f"{suggested_snack} snacks) or raise budget to ~${suggested_budget:.0f}."
        ),
        suggested_budget_nzd=suggested_budget,
        suggested_meals={
            "dinner_count": suggested_dinner,
            "lunch_count": suggested_lunch,
            "snack_count": suggested_snack,
        },
    )
