"""Meal planning: LLM and template-based plan generation."""

from meal_planner.ingredients import deduplicate_ingredients, filter_allergens
from meal_planner.planner import MealPlanner

__all__ = ["MealPlanner", "deduplicate_ingredients", "filter_allergens"]
