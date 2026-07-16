"""Normalize vague LLM ingredient names to shoppable Woolworths terms."""

from __future__ import annotations

# Map vague / unsearchable names to concrete products
_NORMALIZE: dict[str, str] = {
    "mixed seasonal fruits": "apples",
    "seasonal fruits": "apples",
    "seasonal fruit": "apples",
    "mixed fruit": "apples",
    "fresh fruit": "apples",
    "fruit salad": "apples",
    "seasonal vegetables": "stir fry vegetables",
    "seasonal veggies": "stir fry vegetables",
    "seasonal vegetable": "stir fry vegetables",
    "mixed vegetables": "stir fry vegetables",
    "mixed veggies": "stir fry vegetables",
    "vegetable sticks": "carrots",
    "fresh vegetables": "stir fry vegetables",
    "fresh garlic": "garlic",
    "fresh ginger": "ginger",
    "popcorn": "popcorn kernels",
    "green curry": "green curry paste",
    "red curry": "red curry paste",
    "thai green curry": "green curry paste",
    "curry paste": "green curry paste",
    "miso": "miso paste",
    "white miso": "miso paste",
    "bell pepper": "capsicum",
    "bell peppers": "capsicum",
    "fish fillet": "fish fillets",
    "white fish fillets": "fish fillets",
    "white fish fillet": "fish fillets",
    "sustainable white fish fillets": "fish fillets",
    "sustainable white fish fillet": "fish fillets",
    "sustainable fish fillets": "fish fillets",
    "sustainable fish fillet": "fish fillets",
    "fresh broccoli": "broccoli",
    "broccoli florets": "broccoli",
    "mixed salad leaves": "mixed salad greens",
    "salad leaves": "mixed salad greens",
    "mixed greens": "mixed salad greens",
    "red capsicum": "capsicum",
    "green capsicum": "capsicum",
    "yellow capsicum": "capsicum",
    "bell pepper red": "capsicum",
    "taco shell": "taco shells",
    "corn tortillas": "taco shells",
    "tortilla shells": "taco shells",
    "grated cheese": "cheese",
    "shredded cheese": "cheese",
    "cheese grated": "cheese",
    # NZ supermarket naming
    "courgette": "zucchini",
    "pak choy": "bok choy",
    "pakchoi": "bok choy",
    "bokchoi": "bok choy",
    "shanghai pak choy": "bok choy",
    "tinned tomatoes": "diced tomatoes",
    "canned tomatoes": "diced tomatoes",
    "tin tomatoes": "diced tomatoes",
    "canned diced tomatoes": "diced tomatoes",
    "whole wheat wraps": "wholemeal wraps",
    "whole wheat wrap": "wholemeal wraps",
    "wholemeal wrap": "wholemeal wraps",
    "minced beef": "beef mince",
    "beef minced": "beef mince",
    "mince beef": "beef mince",
    "ground beef": "beef mince",
    "long-grain rice": "long grain rice",
    "longgrain rice": "long grain rice",
    "suya spice mix": "cajun seasoning",
    "suya spice": "cajun seasoning",
    "suya": "cajun seasoning",
    "jollof spice mix": "cajun seasoning",
    "jollof spice": "cajun seasoning",
    "jollof seasoning": "cajun seasoning",
    "okra spice mix": "cajun seasoning",
    "okra spice": "cajun seasoning",
    "peanut spice mix": "peanut butter",
    "peanut spice": "peanut butter",
    "groundnut spice mix": "peanut butter",
    # NZ spelling
    "chili flakes": "chilli flakes",
    "chili flake": "chilli flakes",
    "red chili flakes": "chilli flakes",
    "chili powder": "chilli powder",
    "chili": "chilli",
    "carrot": "carrots",
    "kumara mash": "kumara",
    "mashed kumara": "kumara",
    "potato mash": "potatoes",
    "mashed potato": "potatoes",
    "mashed potatoes": "potatoes",
    "lettuce leaves": "lettuce",
    "lettuce leaf": "lettuce",
    "lettuce cups": "lettuce",
    "iceberg lettuce leaves": "lettuce",
    "lemon wedges": "lemons",
    "lemon wedge": "lemons",
    "lemon slices": "lemons",
    "fresh lemon": "lemons",
    "lime wedges": "limes",
    "lime wedge": "limes",
    # Rare NZ produce — Woolworths usually has rocket/spinach instead
    "watercress": "rocket",
    "water cress": "rocket",
    "fresh watercress": "rocket",
    # Rare NZ produce — use kumara as the staple starchy side
    "plantain": "kumara",
    "plantains": "kumara",
    "green plantain": "kumara",
    "ripe plantain": "kumara",
    "fried plantain": "kumara",
    # Recipes often list cooked leftovers — shop the raw/base product instead
    "cooked chicken": "chicken breast",
    "cooked chicken breast": "chicken breast",
    "cooked chicken thighs": "chicken thighs",
    "chicken thigh fillets": "chicken thighs",
    "chicken thigh fillet": "chicken thighs",
    "chicken thighs fillets": "chicken thighs",
    "cooked rice": "rice",
    "cooked jasmine rice": "jasmine rice",
    "cooked brown rice": "brown rice",
    "cooked salmon": "salmon fillets",
    "cooked salmon fillet": "salmon fillets",
    "cooked salmon fillets": "salmon fillets",
}

# LLM compounds that should become separate shop lines
_SPLIT_COMPOUNDS: dict[str, list[tuple[str, float, str]]] = {
    "butter lettuce": [("butter", 50, "g"), ("lettuce", 1, "head")],
}


def normalize_ingredient_name(name: str) -> str:
    key = name.lower().strip()
    # Keep explicit leftover labels so shop logic can skip duplicate protein/carbs
    if key.startswith("leftover ") or key.startswith("left over ") or key.startswith("left-over "):
        return key
    # Drop parenthetical notes: "mixed vegetables (carrots, broccoli)"
    if "(" in key:
        key = key.split("(", 1)[0].strip()
    if key in _NORMALIZE:
        return _NORMALIZE[key]
    if "seasonal fruit" in key:
        return "apples"
    if "seasonal veg" in key:
        return "stir fry vegetables"
    if key.startswith("mixed vegetable"):
        return "stir fry vegetables"
    # "stir-fried" uses fried (not fry); "stir fry" / "stir-fry" use fry
    if (
        "stir" in key
        and ("fry" in key or "fried" in key)
        and "vegetable" in key
        and "sauce" not in key
    ):
        return "stir fry vegetables"
    if "sustainable" in key and "fish" in key and "sauce" not in key:
        return "fish fillets"
    if key in ("white fish", "whitefish") or (
        "white fish" in key and "fillet" in key
    ):
        return "fish fillets"
    if key.endswith(" curry") and "paste" not in key:
        return f"{key} paste"
    # Prepared sides: "X mash" → shop the base produce
    if key.endswith(" mash") and len(key) > 5:
        base = key[: -len(" mash")].strip()
        if base:
            return normalize_ingredient_name(base) if base != key else base
    # Fictional regional spice mixes → Woolworths NZ stand-ins
    if "spice mix" in key or key.endswith(" seasoning mix"):
        if "peanut" in key or "groundnut" in key:
            return "peanut butter"
        return "cajun seasoning"
    if "lemon" in key and any(x in key for x in ("wedge", "slice", "half", "halves")):
        return "lemons"
    if "lime" in key and any(x in key for x in ("wedge", "slice", "half", "halves")):
        return "limes"
    # Slash alternatives from SKU merge ("carrot / carrots") — keep first part
    if " / " in key:
        return normalize_ingredient_name(key.split(" / ", 1)[0].strip())
    return key


def is_fruit_ingredient(name: str) -> bool:
    lower = normalize_ingredient_name(name)
    return lower in {"apples", "pears", "oranges", "bananas", "apple", "pear", "orange", "banana"} or "fruit" in lower


def fruit_fallback_queries() -> list[str]:
    """Cheap in-season fruit to try when a fruit SKU is not found."""
    return ["apples", "pears", "oranges", "bananas"]


def split_compound_ingredients(meals: list) -> list:
    """Split mistaken compound names (e.g. butter lettuce) into separate ingredients."""
    from shared.models import Ingredient, Meal

    for meal in meals:
        if not isinstance(meal, Meal):
            continue
        expanded: list[Ingredient] = []
        for ing in meal.ingredients:
            key = ing.name.lower().strip()
            if key in _SPLIT_COMPOUNDS:
                for name, qty, unit in _SPLIT_COMPOUNDS[key]:
                    expanded.append(
                        Ingredient(
                            name=name,
                            quantity=qty,
                            unit=unit,
                            for_meals=list(ing.for_meals) or [meal.name],
                        )
                    )
            else:
                expanded.append(ing)
        meal.ingredients = expanded
    return meals


def prefers_fresh_produce(name: str) -> bool:
    """True when we should rank fresh over frozen at Woolworths."""
    lower = normalize_ingredient_name(name)
    return lower in {
        "broccoli",
        "capsicum",
        "carrots",
        "carrot",
        "zucchini",
        "courgette",
        "spinach",
        "lettuce",
        "cucumber",
        "tomatoes",
        "tomato",
        "mushrooms",
        "mushroom",
        "cauliflower",
        "beans",
        "peas",
        "corn",
        "asparagus",
        "kale",
        "cabbage",
    }
