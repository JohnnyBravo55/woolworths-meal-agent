"""Pre-cart validation — block wrong-aisle products and mismatched recipe lines."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from shared.allergy import is_product_safe_for_profile, profile_has_gluten_allergy
from shared.gluten_label import GlutenLabelAssessment, GlutenLabelStatus, ProductLabelInfo, assess_gluten_label
from shared.models import GroceryLineItem, MealPlan, UserProfile
from woolworths_adapter.search_helpers import is_plausible_match

# Products that must never match adult meal ingredients
_WRONG_AISLE_TERMS = (
    "baby food",
    "infant formula",
    "follow-on formula",
    "follow on formula",
    "smiling tums",
    "raffertys garden",
    "rafferty's garden",
    "kiddylicious",
    "wattie's baby",
    "only organic stage",
    "s-26",
    "karicare",
    "aptamil",
    "nan supreme",
    "nan optipro",
    "fruit hitz",
    " baby snack",
    " baby pouch",
    " baby rusks",
    " baby cereal",
    " toddler snack",
    "laundry powder",
    "detergent",
    " dishwash",
    "shampoo",
    " nappy",
    " nappies",
    "diaper",
    " baby wipes",
    " pet food",
    "dog treat",
    "cat food",
    "face mask",
    "glow mask",
    "glow lab",
    "hydrating glow",
    "sheet mask",
    "skincare",
    "moisturis",
    "cleanser",
    "body lotion",
)

# Fresh produce — not pouches / infant purees
_FRESH_FRUIT = frozenset({"apple", "apples", "pear", "pears", "banana", "bananas", "orange", "oranges", "peach", "peaches"})

# Also reject canned/brine fish for fresh fillet recipes in cart validation
_FRESH_PRODUCE = frozenset(
    {
        "cucumber",
        "capsicum",
        "bell pepper",
        "bell peppers",
        "zucchini",
        "courgette",
        "broccoli",
        "carrot",
        "carrots",
        "lettuce",
        "tomato",
        "tomatoes",
        "bok choy",
    }
)

_PRODUCE_WRONG_AISLE = (
    "drink",
    "mixer",
    "cordial",
    "hummus",
    "dip",
    "face mask",
    "glow mask",
    "skincare",
    "snacktime",
    "kidney bean",
)

_FRESH_FISH = frozenset({"salmon fillets", "salmon fillet", "fish fillets", "fish fillet"})
_FISH_WRONG = ("in brine", "canned", "tinned", "pouch", "flakes")
_MISO_WRONG = ("instant soup", "soup mix", "cup soup")


@dataclass
class LineValidation:
    ok: bool
    blocked: bool = False
    block_reason: str = ""
    warnings: list[str] = field(default_factory=list)


def validate_product_for_ingredient(
    ingredient_name: str,
    product_name: str,
    brand: str = "",
    *,
    profile: UserProfile | None = None,
    label_assessment: GlutenLabelAssessment | None = None,
) -> LineValidation:
    """Static checks: name match, wrong aisle, allergies (when label known)."""
    ing = ingredient_name.lower()
    combined = f"{product_name} {brand}".lower()
    warnings: list[str] = []

    if not is_plausible_match(ingredient_name, product_name, brand):
        return LineValidation(
            ok=False,
            blocked=True,
            block_reason=f"'{product_name}' does not match recipe ingredient '{ingredient_name}'",
        )

    if not any(x in ing for x in ("baby", "infant", "formula", "nappy")):
        if any(term in combined for term in _WRONG_AISLE_TERMS):
            return LineValidation(
                ok=False,
                blocked=True,
                block_reason=f"Wrong product type for '{ingredient_name}' (baby/pet/household — not a meal ingredient)",
            )

    if ing in _FRESH_FRUIT or any(f in ing.split() for f in _FRESH_FRUIT):
        if any(x in combined for x in ("puree", "pouch", " fruit hitz", "smiling tums")):
            if "sauce" not in ing:
                return LineValidation(
                    ok=False,
                    blocked=True,
                    block_reason=f"Recipe needs fresh fruit, not baby puree/pouch ('{product_name}')",
                )

    if ing in _FRESH_PRODUCE or any(p in ing for p in _FRESH_PRODUCE):
        if any(term in combined for term in _PRODUCE_WRONG_AISLE):
            return LineValidation(
                ok=False,
                blocked=True,
                block_reason=(
                    f"Wrong product type for '{ingredient_name}' "
                    f"(drink/dip/non-produce — not fresh '{ingredient_name}')"
                ),
            )

    if normalize_ing := ingredient_name.lower().strip():
        if normalize_ing in _FRESH_FISH or (
            "salmon" in normalize_ing and "fillet" in normalize_ing
        ):
            if any(term in combined for term in _FISH_WRONG):
                return LineValidation(
                    ok=False,
                    blocked=True,
                    block_reason=f"Recipe needs fresh fish, not canned/brine ('{product_name}')",
                )
        if "miso" in normalize_ing:
            if any(term in combined for term in _MISO_WRONG):
                return LineValidation(
                    ok=False,
                    blocked=True,
                    block_reason=f"Recipe needs miso paste, not instant soup ('{product_name}')",
                )

    if profile and profile_has_gluten_allergy(profile):
        if label_assessment is not None:
            if label_assessment.status == GlutenLabelStatus.CONTAINS:
                return LineValidation(
                    ok=False,
                    blocked=True,
                    block_reason="Contains gluten (ingredient label check)",
                )
            if label_assessment.status == GlutenLabelStatus.TRACES:
                w = label_assessment.user_warning or "May contain traces of gluten"
                if w not in warnings:
                    warnings.append(w)
            elif label_assessment.status == GlutenLabelStatus.UNKNOWN:
                w = label_assessment.user_warning or "Could not verify ingredients — check packaging"
                if w not in warnings:
                    warnings.append(w)
        if not is_product_safe_for_profile(
            product_name,
            brand,
            profile,
            ingredient_name=ingredient_name,
            label_assessment=label_assessment,
        ):
            return LineValidation(
                ok=False,
                blocked=True,
                block_reason="Blocked for allergy profile (product or label)",
            )

    elif profile and not is_product_safe_for_profile(
        product_name, brand, profile, ingredient_name=ingredient_name
    ):
        return LineValidation(
            ok=False,
            blocked=True,
            block_reason="Blocked for allergy profile",
        )

    return LineValidation(ok=True, blocked=False, warnings=warnings)


def validate_against_meal_plan(item: GroceryLineItem, plan: MealPlan | None) -> list[str]:
    """Ensure line item ties back to planned meals."""
    if not plan:
        return []
    issues: list[str] = []
    meal_names = {m.name for m in plan.meals}
    for meal in item.for_meals:
        if meal not in meal_names and meal != "mandatory":
            issues.append(f"Ingredient not linked to a planned meal ({meal})")
    return issues


async def validate_line_item(
    item: GroceryLineItem,
    profile: UserProfile,
    *,
    adapter=None,
    meal_plan: MealPlan | None = None,
) -> LineValidation:
    """Full validation including Woolworths ingredient label when available."""
    label_assessment: GlutenLabelAssessment | None = None
    if adapter and item.sku not in ("OFFLINE", ""):
        try:
            label_info = await adapter.get_product_label(item.sku)
            label_assessment = assess_gluten_label(label_info or ProductLabelInfo())
        except Exception:
            label_assessment = None

    result = validate_product_for_ingredient(
        item.ingredient,
        item.product_name,
        "",
        profile=profile,
        label_assessment=label_assessment,
    )
    for issue in validate_against_meal_plan(item, meal_plan):
        if issue not in result.warnings:
            result.warnings.append(issue)

    if item.sku == "OFFLINE":
        result.warnings.append("No Woolworths product match — add manually")
        return result

    return result


AuditProgressCallback = Callable[[int, int, str], Awaitable[None] | None]


async def _audit_one_item(
    item: GroceryLineItem,
    profile: UserProfile,
    *,
    adapter=None,
    meal_plan: MealPlan | None = None,
) -> GroceryLineItem:
    copy = item.model_copy(deep=True)
    v = await validate_line_item(copy, profile, adapter=adapter, meal_plan=meal_plan)
    copy.warnings = list(dict.fromkeys(copy.warnings + v.warnings))
    if v.blocked:
        copy.cart_blocked = True
        copy.block_reason = v.block_reason
    return copy


async def audit_resolved_list(
    items: list[GroceryLineItem],
    profile: UserProfile,
    *,
    adapter=None,
    meal_plan: MealPlan | None = None,
    on_progress: AuditProgressCallback | None = None,
) -> list[GroceryLineItem]:
    """Validate every shop-list row before cart; set cart_blocked on failures."""
    if not items:
        return []

    audited: list[GroceryLineItem] = []
    batch_size = 5
    total = len(items)

    for start in range(0, total, batch_size):
        batch = items[start : start + batch_size]
        batch_results = await asyncio.gather(
            *(
                _audit_one_item(
                    item,
                    profile,
                    adapter=adapter,
                    meal_plan=meal_plan,
                )
                for item in batch
            )
        )
        audited.extend(batch_results)
        if on_progress:
            done = min(start + len(batch), total)
            maybe = on_progress(done, total, batch[-1].ingredient)
            if maybe is not None:
                await maybe

    return audited


def apply_validation_to_item(item: GroceryLineItem, v: LineValidation) -> GroceryLineItem:
    copy = item.model_copy(deep=True)
    copy.warnings = list(dict.fromkeys(copy.warnings + v.warnings))
    if v.blocked:
        copy.cart_blocked = True
        copy.block_reason = v.block_reason
    return copy
