"""Export shopping lists when cart automation fails."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from shared.models import MealPlan, ResolvedGroceryList


def export_markdown(
    resolved: ResolvedGroceryList,
    meal_plan: MealPlan | None = None,
    output_dir: Path | str = ".",
) -> Path:
    """Write a Markdown shopping list with product links."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"shopping_list_{timestamp}.md"

    lines = [
        "# Woolworths NZ Shopping List",
        "",
        f"**Total:** ${resolved.total:.2f} / ${resolved.budget_nzd:.2f} budget",
        f"**Within budget:** {'Yes' if resolved.within_budget else 'No'}",
        "",
        "## Items",
        "",
        "| Ingredient | Product | Qty | Price | Link |",
        "|------------|---------|-----|-------|------|",
    ]

    for item in resolved.items:
        mandatory = " (mandatory)" if item.is_mandatory else ""
        warn = f" ⚠ {item.warnings[0]}" if item.warnings else ""
        link = f"[View]({item.product_url})" if item.product_url else ""
        lines.append(
            f"| {item.ingredient}{mandatory} | {item.product_name}{warn} | "
            f"{item.quantity} {item.unit} | ${item.line_total:.2f} | {link} |"
        )

    if resolved.unresolved_ingredients:
        lines.extend(["", "## Unresolved (search manually)", ""])
        for name in resolved.unresolved_ingredients:
            lines.append(f"- {name}")

    if resolved.coverage_issues:
        lines.extend(["", "## Recipe coverage gaps", ""])
        for issue in resolved.coverage_issues:
            lines.append(f"- {issue}")

    if meal_plan and meal_plan.meals:
        lines.extend(["", "## Meal Plan", ""])
        for meal in meal_plan.meals:
            lines.append(f"### {meal.day_label}: {meal.name} ({meal.slot.value})")
            lines.append(f"{meal.description}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_csv(
    resolved: ResolvedGroceryList,
    output_dir: Path | str = ".",
) -> Path:
    """Write a CSV shopping list."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"shopping_list_{timestamp}.csv"

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ingredient",
                "sku",
                "product_name",
                "quantity",
                "unit",
                "unit_price",
                "line_total",
                "is_mandatory",
                "in_stock",
                "product_url",
                "for_meals",
                "warnings",
            ],
        )
        writer.writeheader()
        for item in resolved.items:
            writer.writerow(
                {
                    "ingredient": item.ingredient,
                    "sku": item.sku,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                    "is_mandatory": item.is_mandatory,
                    "in_stock": item.in_stock,
                    "product_url": item.product_url,
                    "for_meals": "; ".join(item.for_meals),
                    "warnings": "; ".join(item.warnings),
                }
            )

    return path
