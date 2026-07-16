"""Audit and repair shop-list coverage against meal recipes."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models import Ingredient, Meal, MealSlot, UserProfile

from meal_planner.ingredient_normalize import normalize_ingredient_name
from meal_planner.meal_quality import (
    _CARB,
    _PROTEIN,
    _VEG,
    _has_any,
    _ingredient_text,
    is_leftover_meal,
    leftover_meal_needs_shop,
)
from meal_planner.pantry import is_in_pantry

# Meal title keywords → shoppable ingredient when missing from the recipe list
_TITLE_PROTEIN: list[tuple[tuple[str, ...], tuple[str, float, str]]] = [
    (("beef", "massaman"), ("beef strips", 400, "g")),
    (("beef",), ("beef strips", 400, "g")),
    (("chicken thigh",), ("chicken thighs", 800, "g")),
    (("chicken breast",), ("chicken breast", 400, "g")),
    (("chicken",), ("chicken thighs", 800, "g")),
    (("salmon",), ("salmon fillets", 400, "g")),
    (("fish",), ("fish fillets", 400, "g")),
    (("prawn", "shrimp"), ("prawns", 300, "g")),
    (("pork",), ("pork chops", 400, "g")),
    (("lamb",), ("lamb leg steaks", 400, "g")),
    (("tofu",), ("tofu", 400, "g")),
]

_ROASTED_VEG_MARKERS = ("roasted vegetable", "roast vegetable", "roasted veg", "roast veg")


@dataclass(frozen=True)
class ShopCoverageIssue:
    meal_name: str
    day_label: str
    slot: MealSlot
    kind: str
    detail: str
    missing_ingredients: tuple[str, ...] = ()


def _meal_title_text(meal: Meal) -> str:
    return f"{meal.name} {meal.description}".lower()


def _required_shop_ingredients(meal: Meal, profile: UserProfile) -> list[str]:
    """Non-pantry ingredients this meal should contribute to the shop list."""
    if is_leftover_meal(meal):
        return [
            normalize_ingredient_name(ing.name)
            for ing in meal.ingredients
            if leftover_meal_needs_shop(ing.name)
            and not is_in_pantry(ing.name, profile.pantry_items)
        ]

    return [
        normalize_ingredient_name(ing.name)
        for ing in meal.ingredients
        if not is_in_pantry(ing.name, profile.pantry_items)
    ]


def _meal_needs_shop_items(meal: Meal, profile: UserProfile) -> bool:
    if meal.slot == MealSlot.SNACK:
        return bool(_required_shop_ingredients(meal, profile))
    if is_leftover_meal(meal):
        return bool(_required_shop_ingredients(meal, profile))
    return meal.slot in (MealSlot.DINNER, MealSlot.LUNCH, MealSlot.BREAKFAST)


def infer_ingredients_from_titles(meals: list[Meal], profile: UserProfile) -> list[Meal]:
    """Add ingredients implied by meal names/descriptions but missing from the recipe list."""
    for meal in meals:
        if meal.slot not in (MealSlot.DINNER, MealSlot.LUNCH, MealSlot.BREAKFAST):
            continue
        if is_leftover_meal(meal):
            continue

        title = _meal_title_text(meal)
        ing_text = _ingredient_text(meal)
        existing = {normalize_ingredient_name(i.name) for i in meal.ingredients}

        if not _has_any(ing_text, _PROTEIN):
            for keywords, (name, qty, unit) in _TITLE_PROTEIN:
                if all(k in title for k in keywords):
                    norm = normalize_ingredient_name(name)
                    if norm not in existing:
                        meal.ingredients.append(
                            Ingredient(name=norm, quantity=qty, unit=unit)
                        )
                        existing.add(norm)
                    break

        if any(marker in title for marker in _ROASTED_VEG_MARKERS) and not _has_any(
            ing_text, _VEG
        ):
            for name, qty, unit in (
                ("potato", 2, "each"),
                ("capsicum", 2, "each"),
                ("broccoli", 1, "head"),
            ):
                norm = normalize_ingredient_name(name)
                if norm not in existing:
                    meal.ingredients.append(
                        Ingredient(name=norm, quantity=qty, unit=unit)
                    )
                    existing.add(norm)

        if not _has_any(ing_text, _CARB) and meal.slot == MealSlot.DINNER:
            if "rice" in title and "rice" not in existing:
                meal.ingredients.append(
                    Ingredient(name="jasmine rice", quantity=1, unit="bag")
                )
    return meals


def audit_shop_coverage(
    meals: list[Meal],
    items: list[Ingredient],
    profile: UserProfile,
) -> list[ShopCoverageIssue]:
    """Find meals with no shop lines or missing required ingredients."""
    issues: list[ShopCoverageIssue] = []
    on_list = {normalize_ingredient_name(i.name) for i in items}

    for meal in meals:
        if not _meal_needs_shop_items(meal, profile):
            continue

        required = _required_shop_ingredients(meal, profile)
        linked = [
            i
            for i in items
            if not i.is_mandatory and meal.name in i.for_meals
        ]
        missing = [name for name in required if name not in on_list]

        if not linked:
            issues.append(
                ShopCoverageIssue(
                    meal_name=meal.name,
                    day_label=meal.day_label,
                    slot=meal.slot,
                    kind="no_shop_items",
                    detail="No shopping-list items are linked to this meal.",
                    missing_ingredients=tuple(required),
                )
            )
        elif missing:
            issues.append(
                ShopCoverageIssue(
                    meal_name=meal.name,
                    day_label=meal.day_label,
                    slot=meal.slot,
                    kind="missing_ingredients",
                    detail=f"Recipe needs {', '.join(missing)} but they are not on the shop list.",
                    missing_ingredients=tuple(missing),
                )
            )

        title = _meal_title_text(meal)
        ing_text = _ingredient_text(meal)
        if not is_leftover_meal(meal) and meal.slot in (
            MealSlot.DINNER,
            MealSlot.LUNCH,
        ):
            for keywords, (name, _, _) in _TITLE_PROTEIN:
                if all(k in title for k in keywords) and not _has_any(ing_text, _PROTEIN):
                    norm = normalize_ingredient_name(name)
                    if norm not in on_list:
                        issues.append(
                            ShopCoverageIssue(
                                meal_name=meal.name,
                                day_label=meal.day_label,
                                slot=meal.slot,
                                kind="missing_protein",
                                detail=(
                                    f"Meal title mentions {keywords[0]} but no protein "
                                    "ingredient is on the shop list."
                                ),
                                missing_ingredients=(norm,),
                            )
                        )
                    break

    return issues


def _link_leftover_reuse(
    meals: list[Meal],
    by_name: dict[str, object],
    profile: UserProfile,
) -> None:
    """Attach leftover lunches to existing shop lines they reuse (no extra buy)."""
    for meal in meals:
        if not is_leftover_meal(meal):
            continue
        for ing in meal.ingredients:
            norm = normalize_ingredient_name(ing.name)
            if norm.startswith(("leftover ", "left over ", "left-over ", "steamed ")):
                continue
            if is_in_pantry(ing.name, profile.pantry_items):
                continue
            existing = by_name.get(norm)
            if existing is None:
                continue
            meals_list = getattr(existing, "for_meals", None)
            if meals_list is not None and meal.name not in meals_list:
                meals_list.append(meal.name)


def link_meals_to_shop_items(
    meals: list[Meal],
    items: list[Ingredient],
    profile: UserProfile,
) -> list[Ingredient]:
    """Ensure shared ingredients list every meal that needs them."""
    by_name: dict[str, Ingredient] = {}
    for item in items:
        key = normalize_ingredient_name(item.name)
        if key not in by_name:
            by_name[key] = item
            continue
        existing = by_name[key]
        for meal_name in item.for_meals:
            if meal_name not in existing.for_meals:
                existing.for_meals.append(meal_name)

    for meal in meals:
        for norm in _required_shop_ingredients(meal, profile):
            if norm in by_name and meal.name not in by_name[norm].for_meals:
                by_name[norm].for_meals.append(meal.name)

    _link_leftover_reuse(meals, by_name, profile)
    return list(by_name.values())


def repair_shop_coverage(
    meals: list[Meal],
    items: list[Ingredient],
    profile: UserProfile,
) -> list[Ingredient]:
    """Add missing shop lines and meal links until coverage audit passes."""
    from meal_planner.ingredients import deduplicate_ingredients

    on_list = {normalize_ingredient_name(i.name) for i in items}
    extras: list[Ingredient] = []

    for meal in meals:
        if not _meal_needs_shop_items(meal, profile):
            continue

        for norm in _required_shop_ingredients(meal, profile):
            if norm in on_list:
                continue
            source = next(
                (
                    ing
                    for ing in meal.ingredients
                    if normalize_ingredient_name(ing.name) == norm
                ),
                None,
            )
            if source:
                copy = source.model_copy(deep=True)
            else:
                copy = Ingredient(name=norm, quantity=1.0, unit="each")
            copy.name = norm
            if meal.name not in copy.for_meals:
                copy.for_meals.append(meal.name)
            extras.append(copy)
            on_list.add(norm)

        title = _meal_title_text(meal)
        ing_text = _ingredient_text(meal)
        if not is_leftover_meal(meal) and not _has_any(ing_text, _PROTEIN):
            for keywords, (name, qty, unit) in _TITLE_PROTEIN:
                if all(k in title for k in keywords):
                    norm = normalize_ingredient_name(name)
                    if norm in on_list:
                        break
                    copy = Ingredient(
                        name=norm,
                        quantity=qty,
                        unit=unit,
                        for_meals=[meal.name],
                    )
                    extras.append(copy)
                    on_list.add(norm)
                    break

    merged = deduplicate_ingredients(items + extras)
    return link_meals_to_shop_items(meals, merged, profile)


def format_coverage_issue(issue: ShopCoverageIssue) -> str:
    label = f"{issue.day_label} — {issue.meal_name}" if issue.day_label else issue.meal_name
    if issue.missing_ingredients:
        missing = ", ".join(issue.missing_ingredients)
        return f"{label}: {issue.detail} (need: {missing})"
    return f"{label}: {issue.detail}"


def audit_resolved_shop_coverage(
    meals: list[Meal],
    items: list,
    profile: UserProfile,
) -> list[str]:
    """Check resolved grocery lines still cover every meal."""
    messages: list[str] = []
    on_list = {
        normalize_ingredient_name(getattr(item, "ingredient", getattr(item, "name", "")))
        for item in items
    }
    for meal in meals:
        if not _meal_needs_shop_items(meal, profile):
            continue
        linked = [
            item
            for item in items
            if not getattr(item, "is_mandatory", False) and meal.name in item.for_meals
        ]
        label = f"{meal.day_label} — {meal.name}" if meal.day_label else meal.name
        if not linked:
            messages.append(f"{label}: no shop-list products linked to this meal")
            continue
        missing = [
            name
            for name in _required_shop_ingredients(meal, profile)
            if name not in on_list
        ]
        if missing:
            messages.append(f"{label}: missing from shop list — {', '.join(missing)}")
    return messages


def _coverage_lookup_keys(raw_name: str) -> list[str]:
    """Keys that should resolve to the same shop line (incl. SKU-merge slash names)."""
    raw = (raw_name or "").strip().lower()
    keys: list[str] = []
    parts = [p.strip() for p in raw.split(" / ") if p.strip()] or [raw]
    for part in parts:
        norm = normalize_ingredient_name(part)
        if norm and norm not in keys:
            keys.append(norm)
    return keys


def heal_resolved_coverage(
    meals: list[Meal],
    items: list,
    profile: UserProfile,
) -> tuple[list, list[str]]:
    """Fill holes after product resolve: link meals and add Manual OFFLINE rows.

    Returns (healed_items, remaining_coverage_issues).
    """
    from shared.models import GroceryLineItem
    from woolworths_adapter.estimates import estimate_price

    by_name: dict[str, object] = {}
    for item in items:
        raw = getattr(item, "ingredient", getattr(item, "name", ""))
        keys = _coverage_lookup_keys(str(raw))
        if not keys:
            continue
        primary = keys[0]
        if primary not in by_name:
            by_name[primary] = item
        else:
            existing = by_name[primary]
            for meal_name in getattr(item, "for_meals", []):
                if meal_name not in existing.for_meals:
                    existing.for_meals.append(meal_name)
        # Alias slash segments / synonyms to the same line
        for key in keys:
            by_name[key] = by_name[primary]

    for meal in meals:
        if not _meal_needs_shop_items(meal, profile):
            continue
        for req in _required_shop_ingredients(meal, profile):
            if req in by_name:
                existing = by_name[req]
                if meal.name not in existing.for_meals:
                    existing.for_meals.append(meal.name)
                continue

            unit_price = estimate_price(req)
            by_name[req] = GroceryLineItem(
                ingredient=req,
                sku="OFFLINE",
                product_name=f"{req.title()} (estimated)",
                quantity=1.0,
                unit="Each",
                unit_price=unit_price,
                line_total=round(unit_price, 2),
                for_meals=[meal.name],
                in_stock=True,
                is_mandatory=False,
                product_url="",
                warnings=["No Woolworths product match — add manually"],
            )

    _link_leftover_reuse(meals, by_name, profile)
    # by_name may alias multiple keys to the same line object
    healed = list({id(v): v for v in by_name.values()}.values())
    issues = audit_resolved_shop_coverage(meals, healed, profile)
    return healed, issues
