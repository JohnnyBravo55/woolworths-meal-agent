"""Core data models for intake, meal plans, and grocery resolution."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AgentPhase(str, Enum):
    DISCOVERY = "discovery"
    PLAN_DRAFT = "plan_draft"
    PLAN_APPROVAL = "plan_approval"
    PRODUCT_RESOLUTION = "product_resolution"
    BUDGET_RECONCILIATION = "budget_reconciliation"
    CART = "cart"
    RECIPES = "recipes"
    COMPLETE = "complete"


class BudgetMode(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class BrandPreference(str, Enum):
    BUDGET = "budget"
    MIXED = "mixed"
    PREMIUM = "premium"


class SimplicityLevel(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    AMBITIOUS = "ambitious"


class MealSlot(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class LunchMode(str, Enum):
    """Practical = dinner leftovers for lunch; Original = distinct lunch recipes."""

    PRACTICAL = "practical"
    ORIGINAL = "original"


class MealsRequested(BaseModel):
    breakfast: int = 0
    lunch: int = 0
    dinner: int = 0
    snacks: int = 0

    def total_meals(self) -> int:
        return self.breakfast + self.lunch + self.dinner + self.snacks


class UserProfile(BaseModel):
    household_size: int = Field(ge=1, le=20)
    days: int = Field(default=7, ge=1, le=14)
    meals_requested: MealsRequested
    dietary_preferences: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    mandatory_items: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    likes: list[str] = Field(default_factory=list)
    other_instructions: str = ""
    budget_nzd: float = Field(gt=0)
    budget_mode: BudgetMode = BudgetMode.HARD
    store_id: str = ""
    store_name: str = ""
    simplicity: SimplicityLevel = SimplicityLevel.SIMPLE
    brand_preference: BrandPreference = BrandPreference.MIXED
    assume_pantry_staples: bool = True
    pantry_items: list[str] = Field(default_factory=list)
    leftover_tolerance: Literal["low", "medium", "high"] = "medium"
    lunch_mode: LunchMode = LunchMode.ORIGINAL
    equipment: list[str] = Field(default_factory=list)
    chef_id: str = "basic_sam"

    @field_validator(
        "allergies", "mandatory_items", "dislikes", "likes", "pantry_items", mode="before"
    )
    @classmethod
    def normalize_strings(cls, value: list[str] | None) -> list[str]:
        if not value:
            return []
        return [item.strip().lower() for item in value if item and item.strip()]


class Ingredient(BaseModel):
    name: str
    quantity: float = 1.0
    unit: str = "each"
    notes: str = ""
    for_meals: list[str] = Field(default_factory=list)
    is_mandatory: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip().lower()


class Meal(BaseModel):
    name: str
    slot: MealSlot
    day_label: str
    description: str
    prep_time_minutes: int = 30
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)


class MealPlan(BaseModel):
    meals: list[Meal] = Field(default_factory=list)
    shared_ingredients: list[Ingredient] = Field(default_factory=list)
    estimated_total: float | None = None
    chef_notes: str = ""


class ProductMatch(BaseModel):
    sku: str
    product_name: str
    brand: str = ""
    size: str = ""
    unit_price: float
    sale_price: float | None = None
    is_special: bool = False
    unit: Literal["Each", "Kilogram"] = "Each"
    in_stock: bool = True
    category: str = ""
    cup_price: float | None = None
    cup_measure: str | None = None


class GroceryLineItem(BaseModel):
    ingredient: str
    sku: str
    product_name: str
    quantity: float
    unit: Literal["Each", "Kilogram"] = "Each"
    unit_price: float
    line_total: float
    for_meals: list[str] = Field(default_factory=list)
    in_stock: bool = True
    is_mandatory: bool = False
    product_url: str = ""
    warnings: list[str] = Field(default_factory=list)
    cart_blocked: bool = False
    block_reason: str = ""

    @property
    def effective_unit_price(self) -> float:
        return self.unit_price


class ResolvedGroceryList(BaseModel):
    items: list[GroceryLineItem] = Field(default_factory=list)
    mandatory_subtotal: float = 0.0
    meal_subtotal: float = 0.0
    total: float = 0.0
    budget_nzd: float = 0.0
    within_budget: bool = True
    unresolved_ingredients: list[str] = Field(default_factory=list)
    coverage_issues: list[str] = Field(default_factory=list)

    def addable_items(self) -> list[GroceryLineItem]:
        return [
            i
            for i in self.items
            if i.sku != "OFFLINE" and i.in_stock and not i.cart_blocked
        ]

    def blocked_items(self) -> list[GroceryLineItem]:
        return [i for i in self.items if i.cart_blocked]

    def offline_items(self) -> list[GroceryLineItem]:
        return [i for i in self.items if i.sku == "OFFLINE"]

    @property
    def addable_total(self) -> float:
        return round(sum(i.line_total for i in self.addable_items()), 2)

    @property
    def offline_total(self) -> float:
        return round(sum(i.line_total for i in self.offline_items()), 2)


class ConversationState(BaseModel):
    phase: AgentPhase = AgentPhase.DISCOVERY
    profile: UserProfile | None = None
    meal_plan: MealPlan | None = None
    resolved_list: ResolvedGroceryList | None = None
    plan_approved: bool = False
    products_approved: bool = False
    cart_attempted: bool = False
    cart_success: bool = False
    cart_errors: list[str] = Field(default_factory=list)
    export_paths: list[str] = Field(default_factory=list)

    def advance_to(self, phase: AgentPhase) -> None:
        self.phase = phase
