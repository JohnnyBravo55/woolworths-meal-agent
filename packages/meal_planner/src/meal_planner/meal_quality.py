"""Ensure each meal includes protein, carbohydrate, and vegetables."""

from __future__ import annotations

import re

from shared.allergy import ingredient_conflicts_allergies, profile_has_gluten_allergy
from shared.models import Ingredient, LunchMode, Meal, MealSlot, UserProfile

_PROTEIN = frozenset(
    {
        "chicken",
        "beef",
        "pork",
        "lamb",
        "mince",
        "fish",
        "salmon",
        "tuna",
        "prawn",
        "egg",
        "eggs",
        "tofu",
        "chickpea",
        "chickpeas",
        "lentil",
        "lentils",
        "beans",
        "sausage",
        "bacon",
        "turkey",
        "duck",
        "halloumi",
        "cheese",
        "yoghurt",
        "yogurt",
        "miso",
        "hummus",
    }
)

_CARB = frozenset(
    {
        "rice",
        "pasta",
        "noodle",
        "noodles",
        "potato",
        "potatoes",
        "bread",
        "wrap",
        "wraps",
        "tortilla",
        "quinoa",
        "couscous",
        "taco",
        "crispbread",
        "crackers",
        "oats",
        "muesli",
        "granola",
        "pita",
        "flatbread",
        "baguette",
    }
)

_VEG = frozenset(
    {
        "broccoli",
        "spinach",
        "salad",
        "lettuce",
        "capsicum",
        "bell pepper",
        "carrot",
        "carrots",
        "zucchini",
        "courgette",
        "tomato",
        "tomatoes",
        "cucumber",
        "mushroom",
        "mushrooms",
        "vegetable",
        "vegetables",
        "greens",
        "slaw",
        "peas",
        "corn",
        "cauliflower",
        "cabbage",
        "kale",
        "asparagus",
        "onion",
        "garlic",
        "bok choy",
    }
)

# Snack templates — rotate for variety (not all yoghurt + fruit)
_SNACK_OPTIONS: list[list[tuple[str, float, str]]] = [
    [("apples", 1, "bag"), ("cheese", 1, "block"), ("crackers", 1, "pack")],
    [("greek yoghurt", 1, "tub"), ("bananas", 1, "bunch")],
    [("hummus", 1, "tub"), ("carrots", 1, "bag"), ("crispbread", 1, "pack")],
    [("mixed nuts", 1, "pack"), ("sultanas", 1, "pack")],
    [("berries", 1, "punnet"), ("greek yoghurt", 1, "tub")],
]


def _ingredient_text(meal: Meal) -> str:
    return " ".join(i.name.lower() for i in meal.ingredients)


def _has_any(text: str, keywords: frozenset[str]) -> bool:
    return any(k in text for k in keywords)


def _pick_default(
    options: list[tuple[str, float, str]],
    profile: UserProfile,
) -> tuple[str, float, str] | None:
    for name, qty, unit in options:
        if not ingredient_conflicts_allergies(name, profile):
            return name, qty, unit
    return None


# Whole-word markers only — avoids "preheat" matching "reheat".
_LEFTOVER_WORD_MARKERS = (
    "leftover",
    "leftovers",
    "yesterday",
    "reuse",
    "reheat",
    "reheated",
    "reheating",
)

_LEFTOVER_PHRASE_MARKERS = ("left over", "left-over", "extra from", "extra dinner")

# Only these need a Woolworths search when the meal is leftover-based
_LEFTOVER_LUNCH_SHOP_TERMS = (
    "bread",
    "wrap",
    "tortilla",
    "crispbread",
    "cracker",
    "pita",
    "flatbread",
    "baguette",
    "bun",
    "roll",
)

# Fresh sides still bought for leftover lunches (not duplicate protein/carb)
_LEFTOVER_SIDE_SHOP_TERMS = (
    "salad",
    "lettuce",
    "greens",
    "cucumber",
    "tomato",
    "capsicum",
    "carrot",
    "broccoli",
    "lime",
    "lemon",
    "herbs",
    "coriander",
    "cilantro",
    "mint",
    "avocado",
)

# Binders / coatings for leftover-based dishes (frittata, risotto balls, etc.)
_LEFTOVER_BINDER_SHOP_TERMS = (
    "egg",
    "eggs",
    "butter",
    "cheese",
    "flour",
    "breadcrumb",
    "breadcrumbs",
)


def is_leftover_meal(meal: Meal) -> bool:
    """True when the meal reuses prior cooking rather than needing fresh protein/veg."""
    text = f"{meal.name} {meal.description} {' '.join(meal.steps)}".lower()
    if any(phrase in text for phrase in _LEFTOVER_PHRASE_MARKERS):
        return True
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in _LEFTOVER_WORD_MARKERS)


def leftover_meal_needs_shop(ingredient_name: str) -> bool:
    """Leftover lunches skip duplicate protein/carb but still buy bread and fresh sides."""
    lower = ingredient_name.lower().strip()
    if lower.startswith(("leftover ", "left over ", "left-over ", "steamed ")):
        return False
    if any(term in lower for term in _LEFTOVER_LUNCH_SHOP_TERMS):
        return True
    if any(term in lower for term in _LEFTOVER_SIDE_SHOP_TERMS):
        return True
    # Eggs/butter for frittatas etc. — not leftover protein from the prior meal
    if any(re.search(rf"\b{re.escape(term)}\b", lower) for term in _LEFTOVER_BINDER_SHOP_TERMS):
        return True
    # Duplicate cooked protein / starch from prior meal — do not re-shop
    if any(p in lower for p in _PROTEIN):
        return False
    if any(c in lower for c in ("rice", "pasta", "noodle", "quinoa", "potato", "couscous")):
        return False
    # Condiments / kimchi / sauces / other extras still need buying
    return True


def _is_practical_lunch(meal: Meal, profile: UserProfile) -> bool:
    if meal.slot != MealSlot.LUNCH or profile.lunch_mode != LunchMode.PRACTICAL:
        return False
    return is_leftover_meal(meal)


_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

# Pack/count retail units — already household-sized; never auto-double for leftovers
_PACK_COUNT_UNITS = frozenset(
    {
        "pack",
        "packs",
        "block",
        "blocks",
        "bag",
        "bags",
        "loaf",
        "loaves",
        "punnet",
        "punnets",
        "jar",
        "jars",
        "bottle",
        "bottles",
        "tub",
        "tubs",
    }
)

# Modest bump: dinner already sized for household; ~half again for next-day lunch
_LEFTOVER_PORTION_BUMP = 1.5


def _weekday_index(day_label: str) -> int | None:
    key = (day_label or "").strip().lower()
    try:
        return _WEEKDAYS.index(key)
    except ValueError:
        return None


def _dinners_feeding_next_day_leftover_lunch(meals: list[Meal]) -> set[int]:
    """Return weekday indexes of dinners that feed a next-day leftover lunch."""
    leftover_lunch_days: set[int] = set()
    for meal in meals:
        if meal.slot != MealSlot.LUNCH:
            continue
        if not is_leftover_meal(meal):
            continue
        idx = _weekday_index(meal.day_label)
        if idx is not None:
            leftover_lunch_days.add(idx)
    # Lunch on day D reuses dinner from day D-1
    return {(d - 1) % 7 for d in leftover_lunch_days}


def scale_dinner_portions_for_leftovers(meals: list[Meal], profile: UserProfile) -> list[Meal]:
    """Bump weight protein/carb on dinners that feed a next-day leftover lunch.

    Portions from the planner are already for household size. We only add a modest
    ~1.5× bump for leftovers — never multiply by household_size, and never double
    pack/block retail units (taco packs, cheese blocks, wraps).
    """
    if profile.lunch_mode != LunchMode.PRACTICAL:
        return meals

    feed_days = _dinners_feeding_next_day_leftover_lunch(meals)
    if not feed_days:
        return meals

    weight_units = {"g", "gram", "grams", "kg", "kilogram", "kilograms", "kilo"}
    piece_units = {"each", "fillet", "fillets", "piece", "pieces", "can", "cans"}

    for meal in meals:
        if meal.slot != MealSlot.DINNER:
            continue
        day_idx = _weekday_index(meal.day_label)
        if day_idx is None or day_idx not in feed_days:
            continue
        for ing in meal.ingredients:
            name = ing.name.lower()
            unit = ing.unit.lower().strip()
            if unit in _PACK_COUNT_UNITS:
                continue
            is_protein = any(p in name for p in _PROTEIN)
            is_carb = any(c in name for c in _CARB)
            if not is_protein and not is_carb:
                continue
            # Cheese blocks/toppings are not leftover-scaled staples
            if "cheese" in name:
                continue
            if unit in weight_units or (unit in ("",) and ing.quantity >= 50):
                ing.quantity = round(ing.quantity * _LEFTOVER_PORTION_BUMP, 0)
            elif unit in piece_units:
                bumped = round(ing.quantity * _LEFTOVER_PORTION_BUMP)
                ing.quantity = max(ing.quantity, bumped)
            elif is_protein or is_carb:
                # Unknown unit (e.g. tbsp) — leave alone rather than over-buy
                continue
    return meals


def _defaults_for_missing(
    text: str,
    profile: UserProfile,
    slot: MealSlot,
    *,
    snack_index: int = 0,
    is_practical_lunch: bool = False,
) -> list[Ingredient]:
    adds: list[Ingredient] = []
    gf = profile_has_gluten_allergy(profile)

    if slot == MealSlot.SNACK:
        options = _SNACK_OPTIONS[snack_index % len(_SNACK_OPTIONS)]
        for name, qty, unit in options:
            if ingredient_conflicts_allergies(name, profile):
                continue
            if name not in text:
                adds.append(Ingredient(name=name, quantity=qty, unit=unit))
        return adds

    if is_practical_lunch:
        if not _has_any(text, _CARB):
            saucy = any(
                w in text
                for w in ("curry", "stew", "soup", "braise", "casserole", "tagine", "sauce")
            )
            carb_options = (
                [("rice", 1, "bag"), ("jasmine rice", 1, "bag")]
                if saucy
                else [("bread", 1, "loaf"), ("tortilla wraps", 1, "pack"), ("crispbread", 1, "pack")]
            )
            pick = _pick_default(carb_options, profile)
            if pick:
                adds.append(Ingredient(name=pick[0], quantity=pick[1], unit=pick[2]))
        return adds

    if not _has_any(text, _PROTEIN):
        pick = _pick_default(
            [
                ("chicken breast", 400, "g"),
                ("beef mince", 400, "g"),
                ("tinned tuna", 2, "cans"),
                ("eggs", 6, "each"),
                ("tofu", 400, "g"),
            ],
            profile,
        )
        if pick:
            adds.append(Ingredient(name=pick[0], quantity=pick[1], unit=pick[2]))

    if not _has_any(text, _CARB):
        carb_options: list[tuple[str, float, str]] = [
            ("jasmine rice", 1, "bag"),
            ("potatoes", 1, "kg"),
        ]
        if not gf:
            carb_options.extend([("penne pasta", 500, "g"), ("tortilla wraps", 1, "pack")])
        else:
            carb_options.append(("gluten free pasta", 500, "g"))
        pick = _pick_default(carb_options, profile)
        if pick:
            adds.append(Ingredient(name=pick[0], quantity=pick[1], unit=pick[2]))

    if not _has_any(text, _VEG):
        pick = _pick_default(
            [
                ("broccoli", 1, "head"),
                ("capsicum", 2, "each"),
                ("mixed salad greens", 1, "bag"),
                ("cherry tomatoes", 1, "punnet"),
            ],
            profile,
        )
        if pick:
            adds.append(Ingredient(name=pick[0], quantity=pick[1], unit=pick[2]))

    return adds


def enforce_culinary_coherence(meals: list[Meal]) -> list[Meal]:
    """Fix common LLM mistakes — wrong starches in soups, etc."""
    for meal in meals:
        combined = f"{meal.name} {' '.join(meal.steps)}".lower()
        is_soup = "soup" in combined or "broth" in combined
        if not is_soup:
            continue
        cleaned: list[Ingredient] = []
        for ing in meal.ingredients:
            name = ing.name.lower()
            if name in ("quinoa", "couscous") or "quinoa" in name:
                cleaned.append(ing.model_copy(update={"name": "rice", "unit": "bag", "quantity": 1}))
            else:
                cleaned.append(ing)
        meal.ingredients = cleaned
    return meals


def ensure_meal_balance(meals: list[Meal], profile: UserProfile) -> list[Meal]:
    """Add missing protein, carb, or veg so every main meal is balanced."""
    snack_idx = 0
    for meal in meals:
        if meal.slot == MealSlot.SNACK:
            text = _ingredient_text(meal)
            for ing in _defaults_for_missing(
                text, profile, meal.slot, snack_index=snack_idx
            ):
                if ing.name not in text:
                    meal.ingredients.append(ing)
            snack_idx += 1
            continue

        if meal.slot not in (MealSlot.DINNER, MealSlot.LUNCH, MealSlot.BREAKFAST):
            continue

        practical = _is_practical_lunch(meal, profile)
        text = _ingredient_text(meal)
        for ing in _defaults_for_missing(
            text, profile, meal.slot, is_practical_lunch=practical
        ):
            if ing.name not in text:
                meal.ingredients.append(ing)
    return meals
