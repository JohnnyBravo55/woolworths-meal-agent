"""Generate meal plans from user profiles."""

from __future__ import annotations

import json
import os
from typing import Any


class MealPlanLLMError(Exception):
    """Raised when LLM meal planning fails despite a configured API key."""


from meal_planner.chefs import get_chef, is_premium_chef
from meal_planner.ingredients import build_shopping_ingredients
from meal_planner.ingredient_normalize import split_compound_ingredients
from meal_planner.meal_quality import (
    ensure_meal_balance,
    enforce_culinary_coherence,
    scale_dinner_portions_for_leftovers,
)
from meal_planner.shop_coverage import infer_ingredients_from_titles
from shared.allergy import ingredient_conflicts_allergies, normalize_mandatory_for_allergies
from shared.models import (
    Ingredient,
    LunchMode,
    Meal,
    MealPlan,
    MealSlot,
    SimplicityLevel,
    UserProfile,
)

# Simple template meals for offline / no-API-key fallback
_TEMPLATE_DINNERS = [
    {
        "name": "Honey Soy Chicken Stir-Fry",
        "description": "Quick one-pan stir-fry with rice.",
        "ingredients": [
            ("chicken breast", 500, "g"),
            ("stir fry vegetables", 1, "bag"),
            ("soy sauce", 1, "bottle"),
            ("honey", 1, "jar"),
            ("jasmine rice", 1, "bag"),
        ],
        "steps": [
            "Slice chicken and stir-fry until golden.",
            "Add vegetables and cook 3 minutes.",
            "Stir in soy sauce and honey.",
            "Serve over cooked rice.",
        ],
    },
    {
        "name": "Beef Mince Tacos",
        "description": "Family-friendly tacos ready in 25 minutes.",
        "ingredients": [
            ("beef mince", 500, "g"),
            ("taco shells", 1, "pack"),
            ("salsa", 1, "jar"),
            ("cheese", 1, "block"),
            ("lettuce", 1, "head"),
        ],
        "steps": [
            "Brown mince in a pan.",
            "Warm taco shells.",
            "Fill shells with mince, lettuce, cheese, and salsa.",
        ],
    },
    {
        "name": "Salmon with Roasted Vegetables",
        "description": "Sheet-pan dinner with minimal cleanup.",
        "ingredients": [
            ("salmon fillets", 4, "each"),
            ("potatoes", 1, "kg"),
            ("broccoli", 1, "head"),
            ("olive oil", 1, "bottle"),
            ("lemon", 2, "each"),
        ],
        "steps": [
            "Roast chopped potatoes at 200°C for 25 minutes.",
            "Add broccoli and salmon, roast 12 more minutes.",
            "Squeeze lemon over everything before serving.",
        ],
    },
    {
        "name": "Vegetable Pasta Bake",
        "description": "Creamy baked pasta with hidden veggies.",
        "ingredients": [
            ("penne pasta", 500, "g"),
            ("pasta sauce", 1, "jar"),
            ("mozzarella", 1, "block"),
            ("zucchini", 2, "each"),
            ("mushrooms", 250, "g"),
        ],
        "steps": [
            "Boil pasta until al dente.",
            "Mix with sauce and sautéed vegetables.",
            "Top with cheese and bake 20 minutes at 180°C.",
        ],
    },
    {
        "name": "Pork Sausages with Mash",
        "description": "Classic comfort food, very low effort.",
        "ingredients": [
            ("pork sausages", 1, "pack"),
            ("potatoes", 1, "kg"),
            ("peas", 1, "bag"),
            ("gravy mix", 1, "pack"),
            ("butter", 1, "block"),
        ],
        "steps": [
            "Boil potatoes and mash with butter.",
            "Grill sausages and cook peas.",
            "Prepare gravy and pour over mash and sausages.",
        ],
    },
]

_TEMPLATE_LUNCHES_ORIGINAL = [
    {
        "name": "Chicken Wraps",
        "description": "Prep-ahead wraps with protein and salad.",
        "ingredients": [
            ("tortilla wraps", 1, "pack"),
            ("chicken breast", 300, "g"),
            ("mayonnaise", 1, "jar"),
            ("capsicum", 1, "each"),
            ("mixed salad leaves", 1, "bag"),
        ],
        "steps": ["Cook chicken, slice with capsicum and salad, wrap with mayo."],
    },
    {
        "name": "Tuna Salad Bowls",
        "description": "No-cook lunch with protein and carb.",
        "ingredients": [
            ("tinned tuna", 2, "cans"),
            ("cucumber", 1, "each"),
            ("cherry tomatoes", 1, "punnet"),
            ("crispbread", 1, "pack"),
            ("lemon", 1, "each"),
        ],
        "steps": ["Mix tuna with chopped veg and lemon, serve with crispbread."],
    },
    {
        "name": "Miso Noodle Soup",
        "description": "Light lunch with tofu and greens.",
        "ingredients": [
            ("miso paste", 1, "jar"),
            ("rice noodles", 1, "pack"),
            ("tofu", 300, "g"),
            ("bok choy", 1, "bunch"),
            ("spring onions", 1, "bunch"),
        ],
        "steps": ["Simmer miso broth, cook noodles, add tofu and bok choy."],
    },
]

_TEMPLATE_LUNCHES_PRACTICAL = [
    {
        "name": "Leftover Dinner Wraps",
        "description": "Use extra protein and veg from last night's dinner in wraps.",
        "ingredients": [
            ("tortilla wraps", 1, "pack"),
            ("mixed salad leaves", 1, "bag"),
        ],
        "steps": [
            "Reheat leftover dinner protein and vegetables from yesterday.",
            "Wrap with salad leaves in tortillas — no new protein needed.",
        ],
    },
    {
        "name": "Leftover Sandwich Plates",
        "description": "Turn leftover roast or stir-fry into sandwiches.",
        "ingredients": [
            ("bread", 1, "loaf"),
            ("butter", 1, "block"),
        ],
        "steps": [
            "Slice leftover dinner protein and serve on buttered bread.",
            "Add any leftover salad or veg from the fridge.",
        ],
    },
    {
        "name": "Extra Dinner Portions",
        "description": "Pack an extra portion when cooking dinner — eat as lunch.",
        "ingredients": [],
        "steps": [
            "When cooking tonight's dinner, cook one extra portion.",
            "Reheat tomorrow for lunch — same meal, no extra shopping.",
        ],
    },
]

_TEMPLATE_SNACKS = [
    {
        "name": "Apple, Cheese & Crackers",
        "description": "Simple snack plate.",
        "ingredients": [
            ("apples", 1, "bag"),
            ("cheese", 1, "block"),
            ("crackers", 1, "pack"),
        ],
        "steps": ["Slice apple and cheese, serve with crackers."],
    },
    {
        "name": "Yoghurt & Berries",
        "description": "Quick snack.",
        "ingredients": [
            ("greek yoghurt", 1, "tub"),
            ("berries", 1, "punnet"),
        ],
        "steps": ["Portion yoghurt with berries."],
    },
    {
        "name": "Hummus & Veg Sticks",
        "description": "Crunchy snack.",
        "ingredients": [
            ("hummus", 1, "tub"),
            ("carrots", 1, "bag"),
            ("crispbread", 1, "pack"),
        ],
        "steps": ["Serve hummus with carrot sticks and crispbread."],
    },
    {
        "name": "Nuts & Dried Fruit",
        "description": "Pantry snack.",
        "ingredients": [
            ("mixed nuts", 1, "pack"),
            ("sultanas", 1, "pack"),
        ],
        "steps": ["Portion nuts with sultanas."],
    },
]


_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _template_to_meal(template: dict, slot: MealSlot, day: str, simplicity: SimplicityLevel) -> Meal:
    return Meal(
        name=template["name"],
        slot=slot,
        day_label=day,
        description=template["description"],
        prep_time_minutes=25 if simplicity == SimplicityLevel.SIMPLE else 40,
        ingredients=[
            Ingredient(name=n, quantity=float(q), unit=u) for n, q, u in template["ingredients"]
        ],
        steps=template["steps"],
    )


def _lunch_templates(profile: UserProfile) -> list[dict]:
    if profile.lunch_mode == LunchMode.PRACTICAL:
        return _TEMPLATE_LUNCHES_PRACTICAL
    return _TEMPLATE_LUNCHES_ORIGINAL


def _enforce_meal_counts(plan: MealPlan, profile: UserProfile) -> MealPlan:
    """Pad or trim meals so dinner/lunch/snack counts match the profile request."""
    requested = {
        MealSlot.DINNER: profile.meals_requested.dinner,
        MealSlot.LUNCH: profile.meals_requested.lunch,
        MealSlot.SNACK: profile.meals_requested.snacks,
        MealSlot.BREAKFAST: profile.meals_requested.breakfast,
    }
    templates = {
        MealSlot.DINNER: _TEMPLATE_DINNERS,
        MealSlot.LUNCH: _lunch_templates(profile),
        MealSlot.SNACK: _TEMPLATE_SNACKS,
        MealSlot.BREAKFAST: _TEMPLATE_SNACKS,
    }

    by_slot: dict[MealSlot, list[Meal]] = {s: [] for s in MealSlot}
    for meal in plan.meals:
        by_slot[meal.slot].append(meal)

    result: list[Meal] = []
    day_idx = 0
    for slot in (MealSlot.DINNER, MealSlot.LUNCH, MealSlot.SNACK, MealSlot.BREAKFAST):
        need = requested.get(slot, 0)
        if need <= 0:
            continue
        kept = by_slot[slot][:need]
        pool = templates.get(slot, _TEMPLATE_DINNERS)
        t_idx = 0
        while len(kept) < need:
            template = pool[t_idx % len(pool)]
            day = _DAYS[day_idx % len(_DAYS)]
            day_idx += 1
            kept.append(_template_to_meal(template, slot, day, profile.simplicity))
            t_idx += 1
        for i, meal in enumerate(kept):
            meal.day_label = _DAYS[i % len(_DAYS)]
        result.extend(kept)

    plan.meals = result
    return plan


def _finalize_meals(meals: list[Meal], profile: UserProfile) -> list[Meal]:
    """Balance recipes and infer missing ingredients after count enforcement."""
    meals = infer_ingredients_from_titles(meals, profile)
    meals = ensure_meal_balance(meals, profile)
    meals = scale_dinner_portions_for_leftovers(meals, profile)
    return meals


def _build_plan_shopping_list(plan: MealPlan, profile: UserProfile) -> MealPlan:
    plan.meals = _finalize_meals(plan.meals, profile)
    plan.shared_ingredients = build_shopping_ingredients(plan.meals, profile)
    return plan


def _sanitize_meals_for_profile(meals: list[Meal], profile: UserProfile) -> list[Meal]:
    """Drop allergenic ingredients from each meal."""
    for meal in meals:
        meal.ingredients = [
            ing for ing in meal.ingredients if not ingredient_conflicts_allergies(ing.name, profile)
        ]
    return meals


class MealPlanner:
    """Creates meal plans using LLM when available, templates otherwise."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._last_llm_error: str | None = None

    async def generate(self, profile: UserProfile, *, fallback_on_error: bool = True) -> MealPlan:
        chef = get_chef(profile.chef_id)
        if is_premium_chef(profile.chef_id) and not self.api_key:
            self._last_llm_error = (
                "Premium chefs require OPENAI_API_KEY — add it to your .env file."
            )
            raise MealPlanLLMError(self._last_llm_error)

        if self.api_key:
            try:
                plan = await self._generate_with_llm(profile)
                self._last_llm_error = None
                chef_note = plan.chef_notes or ""
                prefix = f"Planned by {chef.name}, {chef.title}."
                plan.chef_notes = f"{prefix} {chef_note}".strip()
                return plan
            except Exception as exc:
                self._last_llm_error = self._format_llm_error(exc)
                if not fallback_on_error or is_premium_chef(profile.chef_id):
                    raise MealPlanLLMError(self._last_llm_error) from exc
        return self._generate_from_templates(profile, llm_error=self._last_llm_error, chef=chef)

    @staticmethod
    def _format_llm_error(exc: Exception) -> str:
        message = str(exc)
        if "429" in message or "quota" in message.lower():
            return (
                "OpenAI rejected the request — your API key works, but the account "
                "has no credits or billing set up. Add payment at platform.openai.com/settings/billing"
            )
        if "401" in message or "invalid" in message.lower() and "api key" in message.lower():
            return "OpenAI rejected the API key — check it is correct in your .env file."
        return f"OpenAI meal planning failed: {message[:200]}"

    async def _generate_with_llm(self, profile: UserProfile) -> MealPlan:
        from openai import AsyncOpenAI

        chef = get_chef(profile.chef_id)
        client = AsyncOpenAI(api_key=self.api_key)
        prompt = self._build_prompt(profile)

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": chef.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return self._parse_llm_response(data, profile)

    def _build_prompt(self, profile: UserProfile) -> str:
        simplicity_note = {
            SimplicityLevel.SIMPLE: "30 minutes max, 5-7 ingredients per meal",
            SimplicityLevel.MODERATE: "45 minutes max, moderate techniques OK",
            SimplicityLevel.AMBITIOUS: "Complex techniques allowed if user wants",
        }[profile.simplicity]

        mr = profile.meals_requested
        exact_counts = (
            f"You MUST return EXACTLY {mr.dinner} dinners, {mr.lunch} lunches, "
            f"{mr.snacks} snacks, and {mr.breakfast} breakfasts — no fewer, no extras."
        )
        allergy_note = ""
        if profile.allergies:
            allergy_note = (
                f"STRICT ALLERGY RULES for {', '.join(profile.allergies)}: "
                "Never include wheat, bread, pasta, flour, wraps, or soy sauce unless "
                "explicitly labelled gluten-free. No banana bread, muffins, or baked goods "
                "with gluten."
            )
        pantry_note = ""
        if profile.pantry_items:
            pantry_note = (
                "The household ALREADY HAS these items — use them in recipes but do NOT "
                f"list them as shopping ingredients: {', '.join(profile.pantry_items)}."
            )

        lunch_mode_note = ""
        if profile.lunch_mode == LunchMode.PRACTICAL:
            lunch_mode_note = (
                "LUNCH MODE: PRACTICAL — lunches use LEFTOVERS from dinners. "
                "Cook EXTRA portions at dinner (protein and carbs) so lunches can reuse "
                "leftovers for the whole household. Scale protein to cover dinner plus next-day lunch."
                "Do NOT plan completely separate lunch recipes."
            )
        else:
            lunch_mode_note = (
                "LUNCH MODE: ORIGINAL — each lunch is a distinct recipe with its own "
                "protein, carb, and vegetables (same balance rules as dinner)."
            )

        return json.dumps(
            {
                "task": "Create a meal plan",
                "constraints": {
                    "household_size": profile.household_size,
                    "days": profile.days,
                    "meals_requested": profile.meals_requested.model_dump(),
                    "lunch_mode": profile.lunch_mode.value,
                    "lunch_mode_rules": lunch_mode_note,
                    "exact_meal_counts_required": exact_counts,
                    "dietary_preferences": profile.dietary_preferences,
                    "allergies": profile.allergies,
                    "allergy_rules": allergy_note,
                    "mandatory_items": normalize_mandatory_for_allergies(
                        profile.mandatory_items, profile
                    ),
                    "pantry_items_already_at_home": profile.pantry_items,
                    "pantry_rules": pantry_note,
                    "dislikes": profile.dislikes,
                    "likes": profile.likes,
                    "other_instructions": profile.other_instructions,
                    "other_instructions_rules": (
                        "HARD REQUIREMENT: If other_instructions is non-empty, follow those "
                        "instructions for the meal plan (cooking methods, cuisine mix, "
                        "ready-made vs cook-from-scratch, etc.). Only allergies and food-safety "
                        "constraints may override them. Briefly note in chef_notes which "
                        "instructions you applied."
                        if profile.other_instructions.strip()
                        else "No additional user instructions."
                    ),
                    "simplicity": simplicity_note,
                    "assume_pantry_staples": profile.assume_pantry_staples,
                    "meal_balance_rule": (
                        "Each dinner and ORIGINAL lunch needs protein + carb + vegetables "
                        "in the ingredients list. Use concrete shoppable names: capsicum, "
                        "broccoli, green curry paste, miso paste, salmon fillets, fish fillets — "
                        "never vague 'seasonal' items. Prefer FRESH vegetables (broccoli head, "
                        "capsicum each) not frozen unless the recipe is explicitly a freezer meal."
                    ),
                    "snack_rules": (
                        "Vary snacks across the week: rotate fruit+cheese+crackers, yoghurt+berries, "
                        "hummus+veg, nuts+dried fruit — not the same snack every day. "
                        "List every snack ingredient on that snack's ingredient list."
                    ),
                    "ingredient_rules": (
                        "List ONLY ingredients used in each meal's recipe — no extras. "
                        "Include all pastes/sauces (green curry paste, miso paste, etc.). "
                        "Do not put quinoa in soups — use rice or noodles instead. "
                        "Curries need curry paste; Asian soups need miso or stock ingredients named explicitly."
                    ),
                },
                "output_schema": {
                    "meals": [
                        {
                            "name": "string",
                            "slot": "breakfast|lunch|dinner|snack",
                            "day_label": "Monday|Tuesday|...",
                            "description": "string",
                            "prep_time_minutes": "int",
                            "ingredients": [
                                {"name": "string", "quantity": "float", "unit": "string"}
                            ],
                            "steps": ["string"],
                        }
                    ],
                    "chef_notes": (
                        "string — if other_instructions were provided, briefly confirm how "
                        "the plan followed them"
                    ),
                },
            },
            indent=2,
        )

    def _parse_llm_response(self, data: dict[str, Any], profile: UserProfile) -> MealPlan:
        meals: list[Meal] = []
        for item in data.get("meals", []):
            slot_str = item.get("slot", "dinner")
            try:
                slot = MealSlot(slot_str)
            except ValueError:
                slot = MealSlot.DINNER

            ingredients = [
                Ingredient(
                    name=ing["name"],
                    quantity=float(ing.get("quantity", 1)),
                    unit=ing.get("unit", "each"),
                )
                for ing in item.get("ingredients", [])
            ]
            meals.append(
                Meal(
                    name=item["name"],
                    slot=slot,
                    day_label=item.get("day_label", ""),
                    description=item.get("description", ""),
                    prep_time_minutes=int(item.get("prep_time_minutes", 30)),
                    ingredients=ingredients,
                    steps=item.get("steps", []),
                )
            )

        meals = _sanitize_meals_for_profile(meals, profile)
        meals = split_compound_ingredients(meals)
        meals = enforce_culinary_coherence(meals)
        plan = MealPlan(
            meals=meals,
            shared_ingredients=[],
            chef_notes=data.get("chef_notes", ""),
        )
        plan = _enforce_meal_counts(plan, profile)
        return _build_plan_shopping_list(plan, profile)

    def _generate_from_templates(
        self,
        profile: UserProfile,
        llm_error: str | None = None,
        chef=None,
    ) -> MealPlan:
        meals: list[Meal] = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        def add_from_templates(
            templates: list[dict],
            slot: MealSlot,
            count: int,
        ) -> None:
            for i in range(count):
                template = templates[i % len(templates)]
                day = days[i % len(days)]
                ingredients = [
                    Ingredient(name=n, quantity=float(q), unit=u)
                    for n, q, u in template["ingredients"]
                ]
                meals.append(
                    Meal(
                        name=template["name"],
                        slot=slot,
                        day_label=day,
                        description=template["description"],
                        prep_time_minutes=25 if profile.simplicity == SimplicityLevel.SIMPLE else 40,
                        ingredients=ingredients,
                        steps=template["steps"],
                    )
                )

        add_from_templates(_TEMPLATE_DINNERS, MealSlot.DINNER, profile.meals_requested.dinner)
        add_from_templates(_lunch_templates(profile), MealSlot.LUNCH, profile.meals_requested.lunch)
        add_from_templates(_TEMPLATE_SNACKS, MealSlot.SNACK, profile.meals_requested.snacks)

        meals = _sanitize_meals_for_profile(meals, profile)
        meals = split_compound_ingredients(meals)
        meals = enforce_culinary_coherence(meals)
        plan = MealPlan(meals=meals, shared_ingredients=[], chef_notes="")
        plan = _enforce_meal_counts(plan, profile)
        plan = _build_plan_shopping_list(plan, profile)

        chef = chef or get_chef(profile.chef_id)
        notes = (
            f"Offline fallback from {chef.name} ({chef.title}) — fixed template meals. "
            "Add OPENAI_API_KEY to .env for full AI meal planning (Sam uses AI too when configured)."
        )
        if llm_error:
            notes = f"{llm_error}\n\nUsing template meals for now.\n\n{notes}"
        plan.chef_notes = notes
        return plan

    def swap_meal(self, plan: MealPlan, meal_index: int, profile: UserProfile) -> MealPlan:
        """Replace one meal with an alternative from templates."""
        if meal_index < 0 or meal_index >= len(plan.meals):
            return plan

        target = plan.meals[meal_index]
        pool = {
            MealSlot.DINNER: _TEMPLATE_DINNERS,
            MealSlot.LUNCH: _lunch_templates(profile),
            MealSlot.SNACK: _TEMPLATE_SNACKS,
        }.get(target.slot, _TEMPLATE_DINNERS)

        for template in pool:
            if template["name"] != target.name:
                new_meal = Meal(
                    name=template["name"],
                    slot=target.slot,
                    day_label=target.day_label,
                    description=template["description"],
                    prep_time_minutes=target.prep_time_minutes,
                    ingredients=[
                        Ingredient(name=n, quantity=float(q), unit=u)
                        for n, q, u in template["ingredients"]
                    ],
                    steps=template["steps"],
                )
                plan.meals[meal_index] = new_meal
                break

        return _build_plan_shopping_list(plan, profile)
