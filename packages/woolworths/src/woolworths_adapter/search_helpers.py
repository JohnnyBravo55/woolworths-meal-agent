"""NZ grocery search aliases and product match validation."""

from __future__ import annotations

import re

from shared.allergy import profile_has_gluten_allergy
from shared.models import UserProfile

# Ingredient term -> better Woolworths NZ search queries (try in order)
SEARCH_ALIASES: dict[str, list[str]] = {
    "gluten free teriyaki sauce": ["teriyaki sauce gluten free", "kikkoman teriyaki gluten free", "soy sauce gluten free"],
    "teriyaki sauce": ["teriyaki sauce gluten free", "soy sauce gluten free"],
    "gluten free soy sauce": ["soy sauce gluten free", "tamari", "kikkoman tamari"],
    "avocado": ["avocado hass", "avocado each", "avocado loose"],
    "apples": ["apples loose", "apple red"],
    "mixed seasonal fruits": ["apples loose", "pears", "oranges"],
    "seasonal fruits": ["apples loose", "pears"],
    "zucchini": ["courgette fresh", "zucchini each", "zucchini loose"],
    "courgette": ["courgette fresh", "zucchini each"],
    "chicken breast": ["chicken breast skin on", "chicken breast fillet", "chicken breast free range"],
    "chicken thighs": ["chicken thigh fillet", "chicken thigh free range"],
    "chicken thigh fillets": ["chicken thigh fillet", "chicken thigh free range"],
    "chicken thigh fillet": ["chicken thigh fillet", "chicken thigh free range"],
    "chili flakes": ["chilli flakes", "chilli flake", "woolworths chilli flakes"],
    "chilli flakes": ["chilli flakes", "chilli flake", "woolworths chilli flakes"],
    "chili flake": ["chilli flakes", "chilli flake"],
    "lettuce": ["iceberg lettuce", "lettuce fresh", "cos lettuce", "lettuce each"],
    "lettuce leaves": ["iceberg lettuce", "lettuce fresh", "cos lettuce"],
    "lemons": ["lemons loose", "lemon fresh", "lemons each"],
    "lemon wedges": ["lemons loose", "lemon fresh"],
    "limes": ["limes loose", "lime fresh", "limes each"],
    "watercress": ["baby rocket", "rocket salad", "baby spinach"],
    "rocket": ["baby rocket", "rocket salad", "fresh salad rocket"],
    "plantain": ["kumara", "orange kumara", "sweet potato"],
    "plantains": ["kumara", "orange kumara"],
    "salmon fillets": [
        "nz salmon fillets",
        "woolworths nz salmon fillets",
        "salmon fillet skin on",
        "salmon fillet fresh",
        "salmon portions",
        "salmon fillets",
    ],
    "salmon fillet": [
        "nz salmon fillets",
        "salmon fillet skin on",
        "salmon fillet fresh",
        "salmon portions",
    ],
    "salmon": [
        "nz salmon fillets",
        "salmon fillet skin on",
        "salmon fillet fresh",
        "salmon portions",
    ],
    "fish fillets": ["fish fillet fresh", "white fish fillet", "tarakihi fillets", "hoki fillets"],
    "white fish": ["fish fillet fresh", "white fish fillet", "tarakihi fillets"],
    "sustainable white fish fillets": [
        "fish fillet fresh",
        "white fish fillet",
        "tarakihi fillets",
    ],
    "white fish fillets": ["fish fillet fresh", "white fish fillet", "tarakihi fillets"],
    "cod": ["cod fillet fresh"],
    "sushi rice": ["sushi rice", "koshihikari rice", "short grain rice"],
    "cocoa powder": ["cocoa powder baking", "cadbury cocoa"],
    "canned black beans": ["black beans canned", "black beans no added salt"],
    "balsamic vinegar": ["balsamic vinegar"],
    "rice vinegar": ["rice vinegar", "sushi vinegar"],
    "popcorn kernels": ["popcorn kernels", "popcorn popping corn"],
    "bell pepper": ["capsicum", "capsicum red", "capsicum green"],
    "bell peppers": ["capsicum"],
    "stir fry vegetables": [
        "stir fry vegetables",
        "stir fry vegetable mix",
        "frozen stir fry",
        "mixed stir fry vegetables",
    ],
    "stir-fried vegetables": [
        "stir fry vegetables",
        "frozen stir fry",
        "stir fry vegetable mix",
    ],
    "stir fried vegetables": [
        "stir fry vegetables",
        "frozen stir fry",
        "stir fry vegetable mix",
    ],
    "vegetable stir-fry": ["stir fry vegetables", "frozen stir fry", "stir fry vegetable mix"],
    "vegetable stir fry": ["stir fry vegetables", "frozen stir fry", "stir fry vegetable mix"],
    "eggplant": ["aubergine"],
    "nori sheets": ["nori seaweed", "sushi nori"],
    "nori": ["sushi nori"],
    "beef strips": ["beef stir fry", "beef stir fry strips", "beef sizzle steak strips"],
    "beef strip": ["beef stir fry strips"],
    "beef mince": ["beef mince", "nz beef mince", "mince beef"],
    "minced beef": ["beef mince", "nz beef mince", "mince beef"],
    "long grain rice": ["long grain rice", "long-grain rice", "white rice long grain"],
    "long-grain rice": ["long grain rice", "long-grain rice", "white rice long grain"],
    "cajun seasoning": ["cajun seasoning", "cajun spice"],
    "suya spice mix": ["cajun seasoning", "cajun spice"],
    "jollof spice mix": ["cajun seasoning", "cajun spice", "paprika"],
    "okra spice mix": ["cajun seasoning", "cajun spice"],
    "peanut spice mix": ["peanut butter", "peanut butter smooth"],
    "quinoa": ["quinoa grain", "quinoa white"],
    "chopped nuts": ["mixed nuts", "nut mix"],
    "dried fruits": ["dried fruit mix", "sultanas"],
    "mixed berries": ["frozen mixed berries"],
    "nut butter": ["peanut butter smooth"],
    "gluten free bread": ["gluten free bread loaf"],
    "sour cream": ["sour cream original"],
    "feta cheese": ["feta cheese"],
    "canned chickpeas": ["chickpeas canned"],
    "chickpeas": ["chickpeas canned"],
    "cucumber": ["cucumber fresh", "cucumber each", "telegraph cucumber", "fresh vegetable cucumber"],
    "broccoli": ["broccoli head", "broccoli fresh"],
    "capsicum": ["capsicum red", "capsicum green", "fresh vegetable capsicum", "capsicum each", "capsicum"],
    "kimchi": ["kimchi", "kim chi", "korean kimchi"],
    "bok choy": [
        "pak choy",
        "baby pak choy",
        "shanghai pak choy",
        "bok choy",
        "bokchoi",
    ],
    "pak choy": ["pak choy", "baby pak choy", "shanghai pak choy", "bok choy"],
    "tinned tomatoes": ["diced tomatoes", "crushed tomatoes", "canned tomatoes"],
    "canned tomatoes": ["diced tomatoes", "crushed tomatoes"],
    "diced tomatoes": ["diced tomatoes italian", "diced tomatoes", "crushed tomatoes"],
    "whole wheat wraps": ["wholemeal wraps", "wraps wholemeal", "tortilla wraps"],
    "wholemeal wraps": ["wholemeal wraps", "wraps wholemeal", "tortilla wraps"],
    "tortilla wraps": ["tortilla wraps", "wraps", "wholemeal wraps"],
    "green curry paste": ["green curry paste", "thai green curry paste"],
    "red curry paste": ["red curry paste", "thai red curry paste"],
    "miso paste": ["miso paste", "white miso paste"],
    "miso": ["miso paste"],
    "garlic": ["garlic bulb", "garlic fresh"],
    "fresh basil": ["basil fresh", "basil bunch"],
    "basil": ["basil fresh", "basil bunch"],
    "mixed salad greens": ["salad greens", "mesclun", "mixed salad", "mixed salad leaves"],
    "mixed salad leaves": ["mixed salad", "mesclun", "salad greens", "mixed salad greens"],
    "salad leaves": ["mixed salad", "mesclun", "salad greens"],
    "taco shells": ["taco shells", "hard taco shells", "taco kit shells"],
    "taco shell": ["taco shells", "hard taco shells"],
    "crackers": ["crackers", "water crackers", "savoury crackers"],
    "cheese": ["cheese block", "tasty cheese block", "colby cheese block"],
    "cheese snack sticks": ["cheese block", "tasty cheese block"],
    "gluten-free soy sauce": ["soy sauce gluten free", "tamari"],
    "lettuce": ["lettuce iceberg", "lettuce bag"],
    "bananas": ["bananas loose"],
    "oats": ["rolled oats", "oats traditional"],
    "rolled oats": ["rolled oats", "oats traditional"],
    "sesame oil": ["sesame oil", "sesame oil bottle"],
    "olive oil": ["olive oil extra virgin", "olive oil"],
    "coconut oil": ["coconut oil"],
    "yogurt": ["yoghurt", "greek yoghurt", "natural yoghurt"],
    "yoghurt": ["greek yoghurt", "natural yoghurt"],
    "greek yoghurt": ["greek yoghurt", "yoghurt greek"],
    "herbs": ["fresh parsley", "fresh thyme", "mixed herbs fresh"],
    "herbs (thyme or parsley)": ["fresh parsley", "fresh thyme"],
    "parsley": ["fresh parsley", "parsley bunch"],
    "thyme": ["fresh thyme", "thyme fresh"],
    "fresh herbs": ["fresh parsley", "fresh thyme", "mixed herbs fresh"],
    "bread": ["bread white loaf", "bread toast"],
}

# When gluten-free, search these BEFORE the regular alias list
_GF_SEARCH_FIRST: dict[str, list[str]] = {
    "crackers": ["gluten free crackers", "rice crackers", "gluten free rice crackers"],
    "cracker": ["gluten free crackers", "rice crackers"],
    "crispbread": ["gluten free crispbread", "rice cakes thin", "gluten free rice cakes"],
    "taco shells": ["gluten free taco shells", "corn tortillas", "soft taco shells gluten free"],
    "taco shell": ["gluten free taco shells", "corn tortillas"],
    "soy sauce": ["soy sauce gluten free", "tamari", "kikkoman tamari"],
    "bread": ["gluten free bread loaf", "gluten free bread"],
    "wraps": ["gluten free wraps", "corn tortillas"],
    "tortilla wraps": ["gluten free wraps", "corn tortillas"],
    "pasta": ["gluten free pasta", "rice pasta"],
    "penne pasta": ["gluten free penne pasta", "gluten free pasta"],
}

# Chef-specific preferred searches (prepended when relevant)
_CHEF_SEARCH_PREFERENCES: dict[str, dict[str, list[str]]] = {
    "premium_kenji": {
        "crackers": ["rice crackers", "nori rice crackers", "gluten free rice crackers"],
        "cracker": ["rice crackers", "gluten free rice crackers"],
        "soy sauce": ["tamari", "soy sauce gluten free", "kikkoman tamari"],
    },
    "premium_moana": {
        "crackers": ["gluten free crackers", "rice crackers"],
    },
}

# Reject products containing these when ingredient is human food
BLOCKED_PRODUCT_TERMS = frozenset(
    {
        "dog",
        "cat",
        "pet",
        "vitapet",
        "puppy",
        "kitten",
        "munchy strips",
        "dog treat",
        "cat food",
    }
)


# Beauty / personal care — not grocery meal ingredients
_BEAUTY_PERSONAL_TERMS = (
    "face mask",
    "sheet mask",
    "glow mask",
    "hydrating glow mask",
    "glow lab",
    "skincare",
    "moisturis",
    "cleanser",
    " serum ",
    "lipstick",
    "mascara",
    "foundation",
    "face scrub",
    "body lotion",
    "aftershave",
    "deodorant",
    "sunscreen spf",
    "makeup ",
    "cosmetic",
)


def _term_in_text(text: str, term: str) -> bool:
    """Match blocked terms without false positives (e.g. 'pet' in 'petite')."""
    if len(term) <= 3:
        return bool(re.search(rf"\b{re.escape(term)}\b", text))
    return term in text


def _word_in_product(word: str, product_name: str) -> bool:
    """Ingredient token appears in product name (with common plural forms)."""
    name = product_name.replace("-", " ")
    token = word.replace("-", " ")
    if token in name:
        return True
    if word in product_name:
        return True
    if word == "fillets" and "fillet" in product_name:
        return True
    if word == "fillet" and "fillets" in product_name:
        return True
    return False


def search_queries_for(
    ingredient_name: str,
    profile: UserProfile | None = None,
    chef_id: str | None = None,
    *,
    expanded: bool = False,
) -> list[str]:
    """Return search terms to try, most specific first."""
    key = ingredient_name.lower().strip()
    queries: list[str] = []

    if chef_id and chef_id in _CHEF_SEARCH_PREFERENCES:
        chef_prefs = _CHEF_SEARCH_PREFERENCES[chef_id]
        for term, pref_queries in chef_prefs.items():
            if term in key or key == term:
                queries.extend(pref_queries)

    if profile and profile_has_gluten_allergy(profile):
        for term, gf_queries in _GF_SEARCH_FIRST.items():
            if term in key or key == term:
                for q in gf_queries:
                    if q not in queries:
                        queries.append(q)
                break

    if key in SEARCH_ALIASES:
        queries.extend(SEARCH_ALIASES[key])
    queries.append(key)
    # Also try last significant word (e.g. "fresh broccoli" -> "broccoli")
    words = [w for w in key.split() if len(w) > 3 and w not in ("fresh", "dried", "chopped", "canned")]
    if words and words[-1] not in queries:
        queries.append(words[-1])
    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)

    if expanded:
        return _expand_query_variations(out, key)
    return out


def _expand_query_variations(base: list[str], key: str) -> list[str]:
    """Extra search permutations tried automatically before marking an item manual."""
    extras: list[str] = list(base)
    for q in base:
        if "gluten free" in q:
            extras.append(q.replace("gluten free ", "").replace("gluten-free ", ""))
        extras.append(f"{q} woolworths")
        stripped = q.replace("fresh ", "").replace("dried ", "").strip()
        if stripped != q:
            extras.append(stripped)
    words = [w for w in key.split() if len(w) > 2]
    if len(words) >= 2:
        extras.append(" ".join(words[-2:]))
        extras.append(" ".join(words[:2]))
    if words:
        extras.append(words[-1])
        if words[-1].endswith("s"):
            extras.append(words[-1][:-1])
        else:
            extras.append(f"{words[-1]}s")
    # Hyphenated / compound variants (e.g. "taco shells" -> "tacos")
    if " " in key:
        extras.append(key.replace(" ", ""))
    seen: set[str] = set()
    out: list[str] = []
    for q in extras:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


_MEAT_TERMS = frozenset(
    {"beef", "chicken", "pork", "lamb", "salmon", "tuna", "fish", "turkey", "duck", "prawn", "bacon"}
)


def is_plausible_match(ingredient_name: str, product_name: str, brand: str = "") -> bool:
    """Filter obviously wrong Woolworths search results."""
    # NZ spelling: chilli (US chili) — equate before token checks
    ing = ingredient_name.lower().replace("chili", "chilli")
    name = product_name.lower().replace("chili", "chilli")
    combined = f"{product_name} {brand}".lower().replace("chili", "chilli")
    if any(_term_in_text(combined, blocked) for blocked in BLOCKED_PRODUCT_TERMS):
        return False

    # Beauty / personal care aisle — not food (e.g. face masks matching aloe/cucumber)
    if not any(x in ing for x in ("shampoo", "conditioner", "soap", "toothpaste", "deodorant")):
        if any(term in combined for term in _BEAUTY_PERSONAL_TERMS):
            return False

    # Baby / infant / wrong aisle — never for normal meal ingredients
    if not any(x in ing for x in ("baby", "infant", "formula")):
        _wrong_aisle = (
            "baby food",
            "infant formula",
            "smiling tums",
            "raffertys",
            "rafferty",
            "kiddylicious",
            "fruit hitz",
            " baby snack",
            " baby pouch",
            " baby rusks",
            "only organic stage",
        )
        if any(x in combined for x in _wrong_aisle):
            return False

    # Fresh fruit — not puree pouches (baby food)
    _fresh_fruit = ("apple", "apples", "pear", "pears", "banana", "bananas", "orange", "oranges")
    if ing in _fresh_fruit or any(f in ing.split() for f in _fresh_fruit):
        if "sauce" not in ing and any(x in name for x in ("puree", "pouch", "fruit hitz", "smiling tums")):
            return False

    # Oats / grains — not baby food meals
    if "oats" in ing or ing in ("oat", "rolled oats"):
        if "baby food" in combined or "smiling tums" in combined:
            return False

    # Fresh avocado — must be fresh produce, not dressing/oil/dip
    if ing == "avocado" or (
        "avocado" in ing.split() and "oil" not in ing and "dressing" not in ing
    ):
        if any(x in name for x in ("oil", "dressing", "dip", "mayonnaise", "spread", "guacamole")):
            return False
        if "avocado" not in name:
            return False

    # Cheese — prefer blocks over heavily packaged snack sticks
    if ing == "cheese" or (ing.endswith(" cheese") and "cream" not in ing and "feta" not in ing):
        if any(x in name for x in ("stick", "sticks", "snack", "squeezy", "string", "portion pack")):
            return False

    # Crackers — rice / GF products are valid when searching GF variants
    if "cracker" in ing or ing == "crispbread":
        if "rice cracker" in name or "rice cake" in name:
            return True
        if "gluten free" in name or "gf" in name:
            return True

    # Taco shells — must mention taco or tortilla shell
    if "taco shell" in ing or ing == "taco shells":
        if any(x in name for x in ("taco", "tortilla", "shell")):
            return True
        return False

    # Capsicum — fresh veg only, not black pepper, dips, or bean/snack mixes
    if "bell pepper" in ing or ing in ("capsicum", "bell peppers") or ing.endswith(" capsicum"):
        if "black pepper" in name or "white pepper" in name or "pepper ground" in name:
            return False
        if any(
            x in name
            for x in (
                "hummus",
                "dip",
                "spread",
                "sauce",
                "relish",
                "pesto",
                "salsa",
                "cracker",
                "chip",
                "crisp",
                "bean",
                "beans",
                "snacktime",
                "snack",
                "kidney",
            )
        ):
            return False
        if "capsicum" in name and ("with corn" in name or "corn," in name or "corn &" in name):
            return False
        if "capsicum" in name:
            return True
        return False

    # Broccoli — prefer actual broccoli, not unrelated veg
    if ing == "broccoli" or ing.endswith(" broccoli"):
        if "broccoli" not in name and "broccolini" not in name:
            return False

    # Cocoa — not laundry powder
    if "cocoa" in ing and "powder" in ing:
        if "laundry" in name or "detergent" in name or "wash" in name:
            return False
        if "cocoa" not in name and "chocolate" not in name:
            return False

    # Black beans — not baked beans
    if "black beans" in ing:
        if "black" not in name or "bean" not in name:
            return False
        if "baked" in name:
            return False

    # Vinegar types must match
    if "balsamic vinegar" in ing and "balsamic" not in name:
        return False
    if "rice vinegar" in ing and "rice" not in name and "sushi" not in name:
        return False

    # Quinoa grain — not rice mixes or ready meals
    if ing in ("quinoa", "quinoa grain") and "quinoa" in name:
        if any(x in name for x in ("rice", "salad", "microwave", "ready", "meal", "tuna")):
            if "quinoa" in name and "rice" in name:
                return False

    # Popcorn kernels — not microwave bags only
    if "popcorn" in ing and "kernel" in ing:
        if "microwave" in name and "kernel" not in name and "popping" not in name:
            return False

    # Fresh fish — not crumbed, breaded, canned, or fish fingers; fillets must be actual fillets
    _fish_ing = ("salmon", "fish", "tuna", "cod", "haddock", "snapper", "tarakihi")
    if any(x in ing for x in _fish_ing) and "crumb" not in ing and "breaded" not in ing:
        if any(
            x in name
            for x in (
                "crumbed",
                "breaded",
                "battered",
                "tempura",
                "panko",
                "fish finger",
                "fish cake",
                "in brine",
                "canned",
                "tinned",
                " tin ",
                "pouch",
                "flakes",
            )
        ):
            return False
        if "fillet" in ing.split() or "fillets" in ing.split():
            if any(
                x in name
                for x in (
                    "steamed",
                    "hot smoked",
                    "smoked salmon",
                    "canned",
                    "pouch",
                    "vacuum pack",
                    "in brine",
                )
            ):
                return False
            # NZ packs often say "portions" instead of "fillets"
            if "fillet" not in name and "portion" not in name:
                return False
            if "portion" in name and ("salmon" in ing or "fish" in ing):
                return True

    # Miso paste — cooking paste, not instant soup sachets
    if "miso" in ing:
        if any(x in name for x in ("instant soup", "soup mix", "cup soup", "noodle cup", "ramen")):
            return False
        if "paste" in ing and "soup" in name and ("instant" in name or "wakame" in name):
            return False
        if "miso" not in name:
            return False

    # Fresh zucchini / courgette — NZ shelves use "courgette"; reject pickle/jar
    if ing in ("zucchini", "courgette") or (
        "zucchini" in ing.split() and "pickle" not in ing
    ):
        if any(x in name for x in ("pickle", "pickled", "relish", "marinated", "in oil", "in brine")):
            return False
        if "zucchini" in name or "courgette" in name:
            return True
        return False

    # Bok choy — Woolworths NZ labels these as pak choy / shanghai pak choy
    if ing in ("bok choy", "bokchoi", "pak choy", "pakchoi") or ing.endswith(" bok choy"):
        if "choy sum" in name:
            return False
        if any(
            x in name
            for x in ("bok choy", "bokchoi", "pak choy", "pakchoi", "shanghai pak")
        ):
            return True
        return False

    # Tinned/canned tomatoes — NZ products are diced/crushed, rarely "tinned"
    if ing in (
        "tinned tomatoes",
        "canned tomatoes",
        "diced tomatoes",
        "crushed tomatoes",
    ) or "tinned tomato" in ing:
        if "sauce" in name or "paste" in name or "passata" in name:
            return "tomato" in name and any(
                x in name for x in ("sauce", "paste", "passata")
            ) and "diced" not in ing
        if "tomato" in name and any(
            x in name for x in ("diced", "crushed", "sieved", "chopped", "canned")
        ):
            return True
        return False

    # Wholemeal / whole wheat wraps — NZ spelling is wholemeal
    if "wrap" in ing:
        if "wrap" not in name and "tortilla" not in name:
            return False
        if any(x in ing for x in ("wholemeal", "whole wheat", "wholewheat")):
            return any(
                x in name for x in ("wholemeal", "whole wheat", "wholegrain", "multigrain")
            )
        return True

    # Raw chicken — not deli, roast, or pre-cooked products
    _cooked_chicken = (
        "shredded",
        "roast",
        "roasted",
        "cooked",
        "precooked",
        "pre-cooked",
        "smoked",
        "pulled",
        "rotisserie",
        "deli",
        "sandwich",
        "wrap",
        "curry",
        "pie",
        "sausage",
        "nugget",
        "schnitzel",
        "tender",
        "strip",
        "kebab",
        "burger",
        "diced",
        "marinated",
        "souvlaki",
    )
    if "chicken" in ing and not any(x in ing for x in ("stock", "broth", "soup")):
        if any(x in name for x in _cooked_chicken):
            return False
        if "chicken" not in name:
            return False
        if "breast" in ing or ing == "chicken breast":
            if "breast" not in name and "fillet" not in name:
                return False
        if "thigh" in ing and "thigh" not in name:
            return False

    # Chicken breast — not schnitzels, nuggets, etc. (legacy guard)
    if "chicken breast" in ing or ing == "chicken breast":
        if any(
            x in name
            for x in ("schnitzel", "nugget", "tender", "strip", "kebab", "burger", "pie", "sausage", "diced")
        ):
            return False

    # Cucumber — fresh produce only, not pickles / drinks / beauty / dips
    if "cucumber" in ing and "pickle" in name:
        return False
    if ing == "cucumber" or ing.endswith(" cucumber"):
        if "cucumber" not in name:
            return False
        if any(
            x in name
            for x in (
                "mask",
                "lotion",
                "cream",
                "serum",
                "wipe",
                "drink",
                "mixer",
                "cordial",
                "juice",
                "soda",
                "sparkling",
                "yoghurt",
                "yogurt",
                "dip",
                "hummus",
            )
        ):
            return False
        return True

    # Aloe vera — food/grocery only (not skincare)
    if "aloe" in ing:
        if any(x in combined for x in _BEAUTY_PERSONAL_TERMS):
            return False
        if "aloe" not in name and "aloe vera" not in name:
            return False

    # Cooking oils — must match the oil type, not any bottle of oil
    if " oil" in ing or ing.endswith(" oil"):
        oil_type = ing.replace(" oil", "").strip()
        if oil_type and oil_type not in ("cooking", "vegetable"):
            if oil_type not in name:
                return False
        elif "vegetable oil" in ing and "vegetable" not in name and "canola" not in name:
            return False
    if "salad" in ing and "green" in ing and "slaw" in name and "slaw" not in ing:
        return False

    # Nori should not be rice cakes
    if "nori" in ing and "nori" not in name and "seaweed" not in name:
        return False

    # Beef mince — accept "beef mince" for "minced beef" wording
    if ing in ("beef mince", "minced beef", "ground beef", "mince beef"):
        if any(_term_in_text(combined, x) for x in ("treat", "pet", "dog", "cat")):
            return False
        if "beef" in name and "mince" in name:
            return True
        return False

    # Beef strips / stir-fry — NZ packs often say "stir-fry" without "strips"
    if "beef strip" in ing or ing == "beef strips":
        if any(_term_in_text(combined, x) for x in ("treat", "pet", "dog", "cat")):
            return False
        if "beef" not in name and "steak" not in name:
            return False
        if any(
            x in name
            for x in ("strip", "stir-fry", "stir fry", "sizzle", "steak", "diced")
        ):
            return True
        return False
    elif "beef" in ing and "beef" not in name and "steak" not in name:
        return False

    # Soy sauce must not match tomato sauce / ketchup
    if "soy sauce" in ing or ing == "soy sauce":
        if "soy" not in name or "tomato" in name or "ketchup" in name:
            return False

    # Teriyaki should mention teriyaki or soy
    if "teriyaki" in ing and "teriyaki" not in name and "soy" not in name:
        return False

    # Plain pepper spice — not capsicum
    if ing == "pepper" or ing == "black pepper":
        if "capsicum" in name:
            return False

    # Sauce ingredients should not match unrelated sauces
    if ing.endswith(" sauce") and "sauce" in name:
        sauce_type = ing.replace(" sauce", "").strip()
        if sauce_type and sauce_type not in name:
            return False
    if ing in ("quinoa", "quinoa grain") and "salad" not in ing:
        if any(x in name for x in ("tuna", "microwave", "ready", "meal")):
            return False

    # Require at least one meaningful ingredient word in product name
    skip = {"fresh", "dried", "chopped", "canned", "mixed", "sliced", "whole", "free", "range", "gluten"}
    words = [w for w in ing.split() if len(w) > 2 and w not in skip]
    if not words:
        return True

    for meat in _MEAT_TERMS:
        if meat in ing and meat not in name:
            return False

    if len(words) >= 2:
        return all(_word_in_product(w, name) for w in words)
    return _word_in_product(words[0], name)
