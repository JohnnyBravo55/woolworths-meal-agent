"""API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from shared.models import (
    AgentPhase,
    ConversationState,
    MealPlan,
    ResolvedGroceryList,
    UserProfile,
)


class DiscoveryAnswers(BaseModel):
    household_size: int = 2
    days: int = 7
    dinner_count: int = 5
    lunch_count: int = 0
    snack_count: int = 0
    allergies: str = ""
    mandatory_items: str = ""
    pantry_items: str = ""
    likes: str = ""
    dislikes: str = ""
    other_instructions: str = ""
    budget_nzd: float = 0.0
    store_name: str = ""
    simplicity: str = "simple"
    brand_preference: str = "mixed"
    chef_id: str = "basic_sam"
    lunch_mode: str = "original"

    def to_answers_dict(self) -> dict:
        return self.model_dump()


class ProfileSaveRequest(BaseModel):
    name: str
    answers: DiscoveryAnswers


class SwapMealRequest(BaseModel):
    meal_index: int = Field(ge=0)


class WoolworthsLoginRequest(BaseModel):
    """Interactive Woolworths sign-in — polls browser cookies after user signs in."""

    open_browser: bool = True
    timeout_seconds: float = 300.0


class AuthRegisterRequest(BaseModel):
    email: str
    password: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class NdaAcceptRequest(BaseModel):
    full_name: str
    agreed: bool
    nda_version: str = "1"


class CartAddRequest(BaseModel):
    allow_over_budget: bool = False
    export_only: bool = False


class SessionStartResponse(BaseModel):
    session_id: str
    phase: AgentPhase


class WoolworthsStatusResponse(BaseModel):
    connected: bool
    message: str


class WoolworthsCookieItem(BaseModel):
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: float = -1
    httpOnly: bool = False
    secure: bool = False
    sameSite: str = "Lax"


class ImportWoolworthsCookiesRequest(BaseModel):
    cookies: list[WoolworthsCookieItem]


class BudgetSuggestionOut(BaseModel):
    action: str
    ingredient: str
    current_sku: str
    suggested_sku: str | None
    savings: float
    message: str


class CartResultOut(BaseModel):
    success_count: int
    failure_count: int
    skipped_offline: int
    added_total: float
    cart_subtotal: float | None
    session_lost: bool
    errors: list[str]
    export_paths: list[str]
    duplicate_lines_merged: int = 0
    cart_line_count: int | None = None


def cart_result_out(result, export_paths: list[str]) -> CartResultOut:
    return CartResultOut(
        success_count=result.success_count,
        failure_count=result.failure_count,
        skipped_offline=result.skipped_offline,
        added_total=result.added_total,
        cart_subtotal=result.cart_subtotal,
        session_lost=result.session_lost,
        errors=result.errors,
        export_paths=export_paths,
        duplicate_lines_merged=getattr(result, "duplicate_lines_merged", 0),
        cart_line_count=getattr(result, "cart_line_count", None),
    )


class StateResponse(BaseModel):
    phase: AgentPhase
    profile: UserProfile | None
    meal_plan: MealPlan | None
    resolved_list: ResolvedGroceryList | None
    plan_approved: bool
    products_approved: bool
    cart_attempted: bool
    cart_success: bool
    cart_errors: list[str]
    export_paths: list[str]
    budget_suggestions: list[BudgetSuggestionOut]

    @classmethod
    def from_session(cls, session, suggestions=None) -> StateResponse:
        s = session.state
        sug = suggestions or session.budget_suggestions or []
        return cls(
            phase=s.phase,
            profile=s.profile,
            meal_plan=s.meal_plan,
            resolved_list=s.resolved_list,
            plan_approved=s.plan_approved,
            products_approved=s.products_approved,
            cart_attempted=s.cart_attempted,
            cart_success=s.cart_success,
            cart_errors=s.cart_errors,
            export_paths=s.export_paths,
            budget_suggestions=[
                BudgetSuggestionOut(
                    action=x.action,
                    ingredient=x.ingredient,
                    current_sku=x.current_sku,
                    suggested_sku=x.suggested_sku,
                    savings=x.savings,
                    message=x.message,
                )
                for x in sug
            ],
        )
