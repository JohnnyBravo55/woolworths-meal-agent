"""FastAPI application — thin wrapper over MealAgentOrchestrator."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from meal_agent_api.access_gate import AccessCodeMiddleware
from meal_agent_api.auth import user_store
from meal_agent_api.deps import AUTH_COOKIE, SESSION_COOKIE, get_optional_user, get_session
from meal_agent_api.feedback import (
    IF_NEVER_PUBLIC_OPTIONS,
    LIKELIHOOD_OPTIONS,
    MEAL_PLAN_USEFUL_OPTIONS,
    MOST_VALUABLE_OPTIONS,
    append_feedback_to_sheet,
    feedback_store,
    sheets_configured,
)
from meal_agent_api.nda import CURRENT_NDA_VERSION, append_nda_to_sheet, nda_store
from meal_agent_api.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    CartAddRequest,
    CartResultOut,
    DiscoveryAnswers,
    FeedbackSubmitRequest,
    ImportWoolworthsCookiesRequest,
    NdaAcceptRequest,
    WoolworthsLoginRequest,
    ProfileSaveRequest,
    SessionStartResponse,
    StateResponse,
    SwapMealRequest,
    WoolworthsStatusResponse,
    cart_result_out,
)
from woolworths_adapter.session_paths import resolve_woolworths_user_id, woolworths_session_context
from meal_agent_api.session_store import AgentSession, store
from shared.models import AgentPhase, MealSlot, ResolvedGroceryList
from woolworths_adapter.cart_merge import merge_line_items_by_sku


def _woolworths_user_id(session: AgentSession, user) -> str | None:
    return resolve_woolworths_user_id(session.user_id, user.id if user else None)
from woolworths_adapter.cart_validation import audit_resolved_list
from meal_planner.ingredients import build_shopping_ingredients
from meal_planner.shop_coverage import (
    audit_shop_coverage,
    audit_resolved_shop_coverage,
    format_coverage_issue,
    heal_resolved_coverage,
)
from woolworths_adapter.client import WOOLWORTHS_CART_URL, WOOLWORTHS_CART_URL_FALLBACK

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROFILES_DIR = PROJECT_ROOT / "profiles"
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="Woolworths Meal Agent API", version="0.1.0")

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
]


def _cors_origins() -> list[str]:
    raw = os.environ.get("MEAL_AGENT_CORS_ORIGINS", "").strip()
    extra = [o.strip() for o in raw.split(",") if o.strip()]
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    origins: list[str] = []
    for origin in [*_DEFAULT_CORS_ORIGINS, *extra]:
        if origin not in seen:
            seen.add(origin)
            origins.append(origin)
    return origins


# Access gate first, CORS last so it is outermost and labels 401s for browsers.
app.add_middleware(AccessCodeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

CHEFS_STATIC = PROJECT_ROOT / "apps" / "mobile" / "assets" / "chefs"
if not CHEFS_STATIC.is_dir():
    CHEFS_STATIC = PROJECT_ROOT / "apps" / "web" / "public" / "chefs"
if CHEFS_STATIC.is_dir():
    app.mount("/chefs", StaticFiles(directory=str(CHEFS_STATIC)), name="chefs")


def _cookie_secure() -> bool:
    """Cross-origin HTTPS frontends need Secure cookies; local HTTP must not."""
    return os.environ.get("MEAL_AGENT_COOKIE_SECURE", "").strip() == "1"


def _set_session_cookie(response: Response, session_id: str) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="none" if secure else "lax",
        secure=secure,
        max_age=86400 * 7,
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        httponly=True,
        samesite="none" if secure else "lax",
        secure=secure,
        max_age=86400 * 30,
    )


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _sse_response(stream):
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _require_profile(session: AgentSession):
    if not session.state.profile:
        raise HTTPException(status_code=400, detail="Profile not set — complete discovery first")
    return session.state.profile


def _require_plan(session: AgentSession):
    if not session.state.meal_plan:
        raise HTTPException(status_code=400, detail="Meal plan not generated yet")
    return session.state.meal_plan


@app.get("/api/health")
async def health():
    """Public health check — includes whether OpenAI is configured on this API server."""
    from meal_planner.openai_env import openai_api_key_from_env

    load_dotenv(PROJECT_ROOT / ".env", override=True)
    api_key = openai_api_key_from_env()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    return {
        "status": "ok",
        "openai_configured": bool(api_key),
        "openai_model": model,
    }


@app.get("/api/health/openai")
async def health_openai():
    """Probe outbound connectivity to OpenAI (no secrets returned)."""
    from meal_planner.openai_env import openai_api_key_from_env, redact_secrets

    load_dotenv(PROJECT_ROOT / ".env", override=True)
    api_key = openai_api_key_from_env()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    if not api_key:
        return {
            "status": "error",
            "openai_configured": False,
            "openai_model": model,
            "reachable": False,
            "error": "OPENAI_API_KEY is not set on this server",
        }

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, timeout=20.0, max_retries=0)
        await client.models.list()
        return {
            "status": "ok",
            "openai_configured": True,
            "openai_model": model,
            "reachable": True,
            "error": None,
        }
    except Exception as exc:
        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        detail = str(exc).strip() or exc.__class__.__name__
        if cause and str(cause).strip():
            detail = f"{detail} | cause={type(cause).__name__}: {redact_secrets(str(cause).strip())}"
        detail = redact_secrets(detail)
        return {
            "status": "error",
            "openai_configured": True,
            "openai_model": model,
            "reachable": False,
            "error": detail[:500],
            "error_type": type(exc).__name__,
        }


# --- Auth (Phase 2) ---


@app.post("/api/auth/register")
async def auth_register(body: AuthRegisterRequest, response: Response):
    try:
        user = user_store.register(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_auth_cookie(response, user.token)
    return {"email": user.email, "user_id": user.id}


@app.post("/api/auth/login")
async def auth_login(body: AuthLoginRequest, response: Response):
    try:
        user = user_store.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_auth_cookie(response, user.token)
    return {
        "email": user.email,
        "user_id": user.id,
        "is_subscriber": user.is_subscriber,
    }


@app.get("/api/auth/me")
async def auth_me(user=Depends(get_optional_user)):
    if not user:
        return {"authenticated": False, "is_subscriber": False}
    from meal_agent_api.subscription import premium_unlocked

    return {
        "authenticated": True,
        "email": user.email,
        "is_subscriber": user.is_subscriber,
        "premium_unlocked": premium_unlocked(user),
    }


@app.post("/api/auth/logout")
async def auth_logout(response: Response):
    response.delete_cookie(AUTH_COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
async def auth_me(user=Depends(get_optional_user)):
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, "email": user.email, "user_id": user.id}


# --- NDA (hosted beta testers) ---


@app.post("/api/nda/accept")
async def nda_accept(body: NdaAcceptRequest, request: Request):
    name = body.full_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Full legal name is required")
    if not body.agreed:
        raise HTTPException(status_code=400, detail="You must agree to the Agreement to continue")
    version = (body.nda_version or "").strip() or CURRENT_NDA_VERSION
    if version != CURRENT_NDA_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Outdated NDA version. Please refresh and accept version {CURRENT_NDA_VERSION}.",
        )

    client_ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip() or client_ip
    user_agent = request.headers.get("user-agent")

    record = nda_store.append(
        full_name=name,
        nda_version=version,
        user_agent=user_agent,
        client_ip=client_ip,
    )
    try:
        append_nda_to_sheet(record)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "NDA could not be saved to the owner spreadsheet. "
                f"Record id: {record.id}. Please try again or contact the owner."
            ),
        ) from exc

    return {
        "ok": True,
        "id": record.id,
        "full_name": record.full_name,
        "nda_version": record.nda_version,
        "accepted_at": record.accepted_at,
    }


# --- Feedback (hosted beta testers) ---


@app.post("/api/feedback/submit")
async def feedback_submit(body: FeedbackSubmitRequest, request: Request):
    checks = [
        (body.meal_plan_useful, MEAL_PLAN_USEFUL_OPTIONS, "meal_plan_useful"),
        (body.most_valuable, MOST_VALUABLE_OPTIONS, "most_valuable"),
        (body.use_again, LIKELIHOOD_OPTIONS, "use_again"),
        (body.if_never_public, IF_NEVER_PUBLIC_OPTIONS, "if_never_public"),
        (body.premium_subscribe, LIKELIHOOD_OPTIONS, "premium_subscribe"),
    ]
    for value, allowed, field in checks:
        if value not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {field}. Expected one of: {', '.join(allowed)}",
            )

    user_agent = request.headers.get("user-agent")
    record = feedback_store.append(
        session_id=body.session_id or "",
        meal_plan_useful=body.meal_plan_useful,
        most_valuable=body.most_valuable,
        use_again=body.use_again,
        if_never_public=body.if_never_public,
        premium_subscribe=body.premium_subscribe,
        improve=body.improve or "",
        user_agent=user_agent,
    )
    if sheets_configured():
        try:
            append_feedback_to_sheet(record)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Feedback could not be saved to the owner spreadsheet. "
                    f"Record id: {record.id}. Underlying error: {exc}. "
                    "If this mentions full_name or Unauthorized, redeploy the "
                    "Apps Script from docs/nda-google-sheets-apps-script.js "
                    "(Deploy > Manage deployments > New version)."
                ),
            ) from exc

    return {"ok": True, "id": record.id, "submitted_at": record.submitted_at}


# --- Session ---


@app.post("/api/session/start", response_model=SessionStartResponse)
async def session_start(response: Response, user=Depends(get_optional_user)):
    session = store.create(user_id=user.id if user else None)
    _set_session_cookie(response, session.id)
    return SessionStartResponse(session_id=session.id, phase=session.state.phase)


@app.get("/api/session/state", response_model=StateResponse)
async def session_state(session: AgentSession = Depends(get_session)):
    return StateResponse.from_session(session)


# --- Woolworths ---


@app.get("/api/session/woolworths/status", response_model=WoolworthsStatusResponse)
async def woolworths_status(
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    """Woolworths connection for this session (and signed-in app user when applicable)."""
    from woolworths_adapter.client import WoolworthsAdapter
    from woolworths_adapter.login import session_exists

    user_id = resolve_woolworths_user_id(session.user_id, user.id if user else None)
    with woolworths_session_context(user_id):
        if not session_exists():
            return WoolworthsStatusResponse(
                connected=False,
                message="Not connected — sign in via Woolworths in the browser window",
            )
        try:
            connected = await asyncio.wait_for(WoolworthsAdapter().is_live(), timeout=12.0)
        except (asyncio.TimeoutError, Exception):
            connected = False
    if connected:
        return WoolworthsStatusResponse(connected=True, message="Connected to Woolworths NZ")
    return WoolworthsStatusResponse(
        connected=False,
        message=(
            "Not connected — open Woolworths sign-in, complete login, then click Connect again"
        ),
    )


@app.post("/api/session/woolworths/login")
async def woolworths_login(
    body: WoolworthsLoginRequest | None = None,
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    """Open Woolworths in a browser — user signs in on woolworths.co.nz (no password here)."""
    from woolies_cli.browser import AuthError

    from woolworths_adapter.client import WoolworthsAdapter
    from woolworths_adapter.login import session_exists
    from woolworths_adapter.login_subprocess import login_via_subprocess

    opts = body or WoolworthsLoginRequest()
    user_id = resolve_woolworths_user_id(session.user_id, user.id if user else None)

    with woolworths_session_context(user_id):
        if session_exists():
            try:
                connected = await asyncio.wait_for(WoolworthsAdapter().is_live(), timeout=12.0)
            except (asyncio.TimeoutError, Exception):
                connected = False
            if connected:
                return {
                    "connected": True,
                    "message": "Already connected to Woolworths NZ",
                }

    try:
        await login_via_subprocess(
            user_id=user_id,
            timeout_seconds=opts.timeout_seconds,
            open_browser=opts.open_browser,
        )
    except AuthError as exc:
        detail = str(exc).strip() or (
            "Sign-in did not complete. A browser window should open — sign in on "
            "woolworths.co.nz only, then click Connect again."
        )
        raise HTTPException(
            status_code=400,
            detail=f"Woolworths login failed: {detail}",
        ) from exc
    except Exception as exc:
        detail = str(exc).strip() or type(exc).__name__
        raise HTTPException(
            status_code=400,
            detail=f"Login error: {detail}",
        ) from exc

    with woolworths_session_context(user_id):
        try:
            connected = await asyncio.wait_for(WoolworthsAdapter().is_live(), timeout=12.0)
        except (asyncio.TimeoutError, Exception):
            connected = False
    return {
        "connected": connected,
        "message": "Logged in successfully"
        if connected
        else "Login finished but session check failed — click Connect again",
    }


@app.post("/api/session/woolworths/sync")
async def woolworths_sync(
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    """Import Woolworths cookies from the system browser once (for I've signed in)."""
    from woolworths_adapter.client import WoolworthsAdapter
    from woolworths_adapter.cookie_import import import_system_browser_cookies
    from woolworths_adapter.login import session_exists

    user_id = resolve_woolworths_user_id(session.user_id, user.id if user else None)
    with woolworths_session_context(user_id):
        imported = import_system_browser_cookies()
        if not session_exists():
            return {
                "connected": False,
                "message": (
                    "No Woolworths cookies found in Chrome, Edge, or Firefox — sign in at "
                    "woolworths.co.nz in one of those browsers, then try again."
                ),
            }
        if not imported:
            return {
                "connected": False,
                "message": (
                    "Could not refresh cookies from your browser — use Chrome, Edge, or Firefox "
                    "(not Cursor's built-in browser), sign in on woolworths.co.nz, then try again."
                ),
            }
        adapter = WoolworthsAdapter()
        try:
            connected = await asyncio.wait_for(
                adapter.validate_session(retries=1, timeout=8.0),
                timeout=10.0,
            )
        except (asyncio.TimeoutError, Exception):
            connected = False
        if connected:
            return {"connected": True, "message": "Connected to Woolworths NZ"}
        search_ok = False
        try:
            search_ok = await asyncio.wait_for(adapter.probe_search(timeout=8.0), timeout=10.0)
        except (asyncio.TimeoutError, Exception):
            search_ok = False
    if search_ok:
        return {
            "connected": False,
            "message": (
                "Signed in partially — open woolworths.co.nz in the same browser, browse the "
                "shop briefly, then click I've signed in again."
            ),
        }
    return {
        "connected": False,
        "message": (
            "Could not verify Woolworths sign-in — sign in at woolworths.co.nz (click Sign in "
            "on the homepage) using Chrome, Edge, or Firefox, then try again."
        ),
    }


@app.post("/api/session/woolworths/disconnect")
async def woolworths_disconnect(
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    """Clear stored Woolworths cookies for this session (or local session)."""
    from woolworths_adapter.login import disconnect_woolworths_session

    user_id = resolve_woolworths_user_id(session.user_id, user.id if user else None)
    with woolworths_session_context(user_id):
        disconnect_woolworths_session()
    return {
        "connected": False,
        "message": "Woolworths disconnected — session cookies removed",
    }


@app.post("/api/session/woolworths/import-cookies")
async def woolworths_import_cookies(
    body: ImportWoolworthsCookiesRequest,
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    """Accept Woolworths session cookies from mobile WebView sign-in."""
    from woolies_cli.paths import cookies_file, state_dir

    from woolworths_adapter.client import WoolworthsAdapter

    if not body.cookies:
        raise HTTPException(status_code=400, detail="No cookies provided")

    user_id = resolve_woolworths_user_id(session.user_id, user.id if user else None)
    payload = [c.model_dump() for c in body.cookies]

    with woolworths_session_context(user_id):
        state_dir().mkdir(parents=True, exist_ok=True)
        cookies_file().write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            connected = await asyncio.wait_for(WoolworthsAdapter().is_live(), timeout=15.0)
        except (asyncio.TimeoutError, Exception):
            connected = False

    if not connected:
        return {
            "connected": False,
            "message": (
                "Cookies saved but Woolworths session not verified yet — "
                "finish signing in on woolworths.co.nz, then tap I've signed in again"
            ),
        }
    return {"connected": True, "message": "Connected to Woolworths NZ"}


# --- Profiles ---


@app.get("/api/profiles")
async def list_profiles():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profiles = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profiles.append({"id": path.stem, "name": data.get("name", path.stem), "path": str(path)})
        except Exception:
            profiles.append({"id": path.stem, "name": path.stem, "path": str(path)})
    return {"profiles": profiles}


@app.get("/api/profiles/{profile_id}")
async def get_profile(profile_id: str):
    path = PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/profiles")
async def save_profile(body: ProfileSaveRequest):
    from agent.conversation import ConversationManager

    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    slug = body.name.lower().replace(" ", "_")[:40]
    path = PROFILES_DIR / f"{slug}.json"
    ConversationManager.save_answers(path, body.answers.to_answers_dict(), name=body.name)
    return {"id": slug, "path": str(path)}


@app.post("/api/profile")
async def set_profile(
    body: DiscoveryAnswers,
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    from meal_planner.chefs import is_premium_chef
    from meal_agent_api.subscription import premium_unlocked

    if is_premium_chef(body.chef_id) and not premium_unlocked(user):
        raise HTTPException(
            status_code=403,
            detail="Premium chefs require an active subscription. Sign in as a subscriber or use Sam (Basic).",
        )
    profile = await session.orchestrator.run_discovery(body.to_answers_dict())
    return {"profile": profile, "state": StateResponse.from_session(session)}


@app.get("/api/chefs")
async def list_chefs(user=Depends(get_optional_user)):
    from meal_planner.chefs import list_chefs as all_chefs
    from meal_planner.chefs import chef_to_public_dict
    from meal_agent_api.subscription import premium_unlocked

    unlocked = premium_unlocked(user)
    chefs = [chef_to_public_dict(c) for c in all_chefs()]
    return {"chefs": chefs, "premium_unlocked": unlocked}


# --- Plan ---


@app.post("/api/plan/generate")
async def plan_generate(
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    from meal_planner.chefs import is_premium_chef
    from meal_agent_api.subscription import premium_unlocked
    from meal_planner.planner import MealPlanLLMError

    profile = _require_profile(session)
    if is_premium_chef(profile.chef_id) and not premium_unlocked(user):
        raise HTTPException(status_code=403, detail="Premium chef requires subscription")

    async def stream():
        from meal_planner.budget_feasibility import check_budget_feasibility

        yield _sse_event("status", {"message": "Checking budget…", "done": 1, "total": 5})
        feasibility = check_budget_feasibility(profile)
        if not feasibility.feasible:
            yield _sse_event(
                "warning",
                {
                    "message": feasibility.message,
                    "suggested_budget_nzd": feasibility.suggested_budget_nzd,
                    "suggested_meals": feasibility.suggested_meals,
                },
            )
        yield _sse_event(
            "status",
            {"message": "Consulting your chef…", "done": 2, "total": 5, "phase": "generate"},
        )
        try:
            # Heartbeats while the LLM runs — keeps proxies from closing idle SSE streams.
            task = asyncio.create_task(session.orchestrator.generate_plan(profile))
            while not task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=8.0)
                except asyncio.TimeoutError:
                    yield _sse_event(
                        "status",
                        {
                            "message": "Still cooking with your chef…",
                            "done": 3,
                            "total": 5,
                            "phase": "generate",
                        },
                    )
            plan = await task
            yield _sse_event(
                "status",
                {"message": "Balancing meals & building shop list…", "done": 4, "total": 5},
            )
            llm_err = session.orchestrator.planner._last_llm_error
            if llm_err:
                yield _sse_event("warning", {"message": llm_err})
            yield _sse_event(
                "complete",
                {
                    "meal_plan": plan.model_dump(mode="json"),
                    "state": StateResponse.from_session(session).model_dump(mode="json"),
                },
            )
        except MealPlanLLMError as exc:
            yield _sse_event("error", {"message": str(exc)})
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    return _sse_response(stream())


@app.get("/api/plan")
async def get_plan(session: AgentSession = Depends(get_session)):
    plan = _require_plan(session)
    return {"meal_plan": plan}


@app.post("/api/plan/approve")
async def plan_approve(session: AgentSession = Depends(get_session)):
    _require_plan(session)
    session.orchestrator.approve_plan(True)
    slot_order = {
        MealSlot.BREAKFAST: 0,
        MealSlot.LUNCH: 1,
        MealSlot.SNACK: 2,
        MealSlot.DINNER: 3,
    }
    meals = sorted(
        session.state.meal_plan.meals,
        key=lambda m: (m.day_label or "", slot_order.get(m.slot, 9), m.name),
    )
    return {
        "meals": [m.model_dump(mode="json") for m in meals],
        "dinners": [m.model_dump(mode="json") for m in meals if m.slot == MealSlot.DINNER],
        "state": StateResponse.from_session(session),
    }


@app.post("/api/plan/swap")
async def plan_swap(body: SwapMealRequest, session: AgentSession = Depends(get_session)):
    profile = _require_profile(session)
    plan = _require_plan(session)
    if body.meal_index >= len(plan.meals):
        raise HTTPException(status_code=400, detail="Invalid meal index")
    new_plan = session.orchestrator.planner.swap_meal(plan, body.meal_index, profile)
    session.state.meal_plan = new_plan
    session.state.resolved_list = None
    session.budget_suggestions = []
    session.state.products_approved = False
    return {"meal_plan": new_plan, "state": StateResponse.from_session(session)}


@app.post("/api/plan/regenerate")
async def plan_regenerate(session: AgentSession = Depends(get_session)):
    profile = _require_profile(session)
    plan = await session.orchestrator.generate_plan(profile)
    session.state.resolved_list = None
    session.budget_suggestions = []
    session.state.products_approved = False
    return {"meal_plan": plan, "state": StateResponse.from_session(session)}


@app.get("/api/plan/recipes/download")
async def download_recipes(session: AgentSession = Depends(get_session)):
    from agent.review import ReviewGate

    plan = _require_plan(session)
    text = ReviewGate.format_recipes(plan)
    return Response(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="recipes.md"'},
    )


# --- Shop ---


@app.post("/api/shop/resolve")
async def shop_resolve(
    force: bool = False,
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    profile = _require_profile(session)
    plan = _require_plan(session)
    if not session.state.plan_approved:
        raise HTTPException(status_code=400, detail="Approve meal plan first")

    orch = session.orchestrator
    ww_user = _woolworths_user_id(session, user)
    with woolworths_session_context(ww_user):
        if await orch.adapter.is_session_available():
            orch.resolver.offline_mode = False
        else:
            orch.resolver.offline_mode = True

    if session.state.resolved_list and not force:

        async def cached_stream():
            resolved = session.state.resolved_list
            suggestions = session.budget_suggestions or []
            yield _sse_event(
                "status",
                {"message": "Using cached shop list", "cached": True},
            )
            yield _sse_event(
                "complete",
                {
                    "resolved_list": resolved.model_dump(mode="json"),
                    "suggestions": [
                        {
                            "action": s.action,
                            "ingredient": s.ingredient,
                            "current_sku": s.current_sku,
                            "suggested_sku": s.suggested_sku,
                            "savings": s.savings,
                            "message": s.message,
                        }
                        for s in suggestions
                    ],
                    "state": StateResponse.from_session(session, suggestions).model_dump(mode="json"),
                    "cached": True,
                },
            )

        return _sse_response(cached_stream())

    ingredients = build_shopping_ingredients(plan.meals, profile)
    plan.shared_ingredients = ingredients
    # Resolve proteins early — perishable search results flake more under load
    _protein_first = (
        "salmon",
        "chicken",
        "beef",
        "pork",
        "lamb",
        "fish",
        "mince",
        "tofu",
    )

    def _resolve_priority(ing) -> tuple[int, str]:
        name = ing.name.lower()
        if any(p in name for p in _protein_first):
            return (0, name)
        if ing.is_mandatory:
            return (2, name)
        return (1, name)

    ingredients = sorted(ingredients, key=_resolve_priority)
    total = len(ingredients)

    async def stream():
        with woolworths_session_context(ww_user):
            if orch.resolver.offline_mode:
                yield _sse_event(
                    "status",
                    {
                        "message": "Using estimated prices — sign in at Add to cart for live Woolworths search",
                        "total": total,
                        "done": 0,
                    },
                )
            else:
                yield _sse_event("status", {"message": "Searching Woolworths…", "total": total, "done": 0})
            items = []
            unresolved = []
            for idx, ingredient in enumerate(ingredients, start=1):
                try:
                    if idx > 1:
                        # Pace Woolworths search — batch resolve flakes under burst load
                        await asyncio.sleep(0.35)
                    line = await orch.resolver.resolve_ingredient(
                        ingredient, profile, meal_plan=plan
                    )
                    if line:
                        items.append(line)
                        status = "offline" if line.sku == "OFFLINE" else "ok"
                    else:
                        unresolved.append(ingredient.name)
                        status = "error"
                    yield _sse_event(
                        "progress",
                        {
                            "ingredient": ingredient.name,
                            "status": status,
                            "done": idx,
                            "total": total,
                            "sku": line.sku if line else None,
                        },
                    )
                except Exception as exc:
                    unresolved.append(ingredient.name)
                    yield _sse_event(
                        "progress",
                        {
                            "ingredient": ingredient.name,
                            "status": "error",
                            "done": idx,
                            "total": total,
                            "error": str(exc),
                        },
                    )

            # Second pass: re-resolve OFFLINE rows after a cool-down (search flakiness)
            offline_names = {i.ingredient.lower() for i in items if i.sku == "OFFLINE"}
            if offline_names and not orch.resolver.offline_mode:
                yield _sse_event(
                    "status",
                    {
                        "message": f"Retrying {len(offline_names)} unresolved products…",
                        "phase": "retry",
                    },
                )
                await asyncio.sleep(3.0)
                by_name = {ing.name.lower(): ing for ing in ingredients}
                # Retry proteins first — salmon/fish search flakes hardest under load
                _retry_priority = (
                    "salmon",
                    "fish",
                    "chicken",
                    "beef",
                    "pork",
                    "lamb",
                    "mince",
                )

                def _offline_retry_key(line) -> tuple[int, str]:
                    n = line.ingredient.lower()
                    if any(p in n for p in _retry_priority):
                        return (0, n)
                    return (1, n)

                offline_lines = sorted(
                    [i for i in items if i.sku == "OFFLINE"],
                    key=_offline_retry_key,
                )
                offline_resolved: dict[str, object] = {}
                for line in offline_lines:
                    source = by_name.get(line.ingredient.lower())
                    if source is None:
                        continue
                    retry_line = None
                    for _attempt in range(3):
                        try:
                            retry_line = await orch.resolver.resolve_ingredient(
                                source, profile, meal_plan=plan
                            )
                        except Exception:
                            retry_line = None
                        if retry_line and retry_line.sku != "OFFLINE":
                            break
                        await asyncio.sleep(2.0)
                    if retry_line and retry_line.sku != "OFFLINE":
                        offline_resolved[line.ingredient.lower()] = retry_line
                        yield _sse_event(
                            "progress",
                            {
                                "ingredient": retry_line.ingredient,
                                "status": "ok",
                                "sku": retry_line.sku,
                                "phase": "retry",
                            },
                        )
                    # Brief pause between offline retries to ease Woolworths rate limits
                    await asyncio.sleep(0.75)

                refreshed: list = []
                for line in items:
                    if line.sku == "OFFLINE" and line.ingredient.lower() in offline_resolved:
                        refreshed.append(offline_resolved[line.ingredient.lower()])
                    else:
                        refreshed.append(line)
                items = refreshed

            mandatory_subtotal = sum(i.line_total for i in items if i.is_mandatory)
            meal_subtotal = sum(i.line_total for i in items if not i.is_mandatory)
            total_sum = round(mandatory_subtotal + meal_subtotal, 2)
            resolved = ResolvedGroceryList(
                items=items,
                mandatory_subtotal=round(mandatory_subtotal, 2),
                meal_subtotal=round(meal_subtotal, 2),
                total=total_sum,
                budget_nzd=profile.budget_nzd,
                within_budget=round(sum(i.line_total for i in items if i.sku != "OFFLINE"), 2)
                <= profile.budget_nzd,
                unresolved_ingredients=unresolved,
            )
            items, _ = merge_line_items_by_sku(resolved.items)

            yield _sse_event(
                "status",
                {
                    "message": "Checking products match your recipes…",
                    "phase": "validate",
                    "done": 0,
                    "total": len(items),
                },
            )

            progress_queue: asyncio.Queue[tuple[int, int, str]] = asyncio.Queue()

            async def on_audit_progress(done: int, total_items: int, ingredient: str) -> None:
                await progress_queue.put((done, total_items, ingredient))

            audit_task = asyncio.create_task(
                audit_resolved_list(
                    items,
                    profile,
                    adapter=orch.adapter,
                    meal_plan=plan,
                    on_progress=on_audit_progress,
                )
            )

            while not audit_task.done():
                try:
                    done, total_items, ingredient = await asyncio.wait_for(
                        progress_queue.get(), timeout=0.25
                    )
                    yield _sse_event(
                        "progress",
                        {
                            "ingredient": ingredient,
                            "status": "validating",
                            "done": done,
                            "total": total_items,
                            "phase": "validate",
                        },
                    )
                except asyncio.TimeoutError:
                    if audit_task.done():
                        break

            while not progress_queue.empty():
                done, total_items, ingredient = progress_queue.get_nowait()
                yield _sse_event(
                    "progress",
                    {
                        "ingredient": ingredient,
                        "status": "validating",
                        "done": done,
                        "total": total_items,
                        "phase": "validate",
                    },
                )

            items = await audit_task
            items, heal_issues = heal_resolved_coverage(plan.meals, items, profile)
            items = await audit_resolved_list(
                items, profile, adapter=None, meal_plan=plan
            )
            coverage_issues: list[str] = list(heal_issues)
            for issue in audit_shop_coverage(plan.meals, ingredients, profile):
                msg = format_coverage_issue(issue)
                if msg not in coverage_issues:
                    coverage_issues.append(msg)
            for message in audit_resolved_shop_coverage(plan.meals, items, profile):
                if message not in coverage_issues:
                    coverage_issues.append(message)
            resolved = resolved.model_copy(
                update={"items": items, "coverage_issues": coverage_issues}
            )
            orch.state.resolved_list = resolved
            orch.state.advance_to(AgentPhase.BUDGET_RECONCILIATION)

            yield _sse_event(
                "status",
                {"message": "Reconciling budget…", "phase": "budget", "done": total, "total": total},
            )
            resolved, suggestions = await orch.reconcile_budget(resolved, profile)
            session.budget_suggestions = suggestions

            # Budget trim + coverage heal can leave OFFLINE proteins — re-resolve them
            offline_after = [i for i in resolved.items if i.sku == "OFFLINE"]
            if offline_after and not orch.resolver.offline_mode:
                by_name = {ing.name.lower(): ing for ing in ingredients}
                fixed: list = []
                for line in resolved.items:
                    if line.sku != "OFFLINE":
                        fixed.append(line)
                        continue
                    source = by_name.get(line.ingredient.lower())
                    if source is None:
                        from shared.models import Ingredient as _Ing

                        source = _Ing(
                            name=line.ingredient,
                            quantity=line.quantity,
                            unit="each",
                            for_meals=list(line.for_meals),
                        )
                    try:
                        retry_line = await orch.resolver.resolve_ingredient(
                            source, profile, meal_plan=plan
                        )
                    except Exception:
                        retry_line = None
                    if retry_line and retry_line.sku != "OFFLINE":
                        # Keep meal links from the heal placeholder
                        for meal in line.for_meals:
                            if meal not in retry_line.for_meals:
                                retry_line.for_meals.append(meal)
                        fixed.append(retry_line)
                    else:
                        fixed.append(line)
                resolved = orch.budget_engine._recalculate(fixed, profile).model_copy(
                    update={
                        "coverage_issues": list(resolved.coverage_issues or []),
                        "unresolved_ingredients": list(
                            resolved.unresolved_ingredients or []
                        ),
                    }
                )
                orch.state.resolved_list = resolved

            yield _sse_event(
                "complete",
                {
                    "resolved_list": resolved.model_dump(mode="json"),
                    "budget_suggestions": [
                        {
                            "action": s.action,
                            "ingredient": s.ingredient,
                            "current_sku": s.current_sku,
                            "suggested_sku": s.suggested_sku,
                            "savings": s.savings,
                            "message": s.message,
                        }
                        for s in suggestions
                    ],
                    "state": StateResponse.from_session(session, suggestions).model_dump(mode="json"),
                },
            )

    return _sse_response(stream())


@app.get("/api/shop/list")
async def shop_list(session: AgentSession = Depends(get_session)):
    if not session.state.resolved_list:
        raise HTTPException(status_code=400, detail="Resolve products first")
    return {"resolved_list": session.state.resolved_list, "suggestions": session.budget_suggestions}


@app.post("/api/shop/approve")
async def shop_approve(session: AgentSession = Depends(get_session)):
    if not session.state.resolved_list:
        raise HTTPException(status_code=400, detail="No shop list")
    session.orchestrator.approve_products(True)
    return {"state": StateResponse.from_session(session)}


# --- Cart ---


@app.post("/api/cart/add", response_model=CartResultOut)
async def cart_add(
    body: CartAddRequest,
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    resolved = session.state.resolved_list
    if not resolved:
        raise HTTPException(status_code=400, detail="No shop list")

    session.export_only = body.export_only
    if body.export_only:
        paths = await session.orchestrator.export_only(resolved)
        session.state.advance_to(AgentPhase.COMPLETE)
        return CartResultOut(
            success_count=0,
            failure_count=0,
            skipped_offline=len(resolved.offline_items()),
            added_total=0,
            cart_subtotal=None,
            session_lost=False,
            errors=[],
            export_paths=paths,
        )

    if not session.state.products_approved:
        raise HTTPException(status_code=400, detail="Approve shop list first")

    try:
        with woolworths_session_context(_woolworths_user_id(session, user)):
            result = await session.orchestrator.add_to_cart(
                resolved,
                plan_approved=session.state.plan_approved,
                products_approved=session.state.products_approved,
                allow_over_budget=body.allow_over_budget,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session.last_cart_result = result
    session.state.advance_to(AgentPhase.COMPLETE)
    return cart_result_out(result, session.state.export_paths)


@app.post("/api/cart/add-after-approve")
async def cart_add_after_approve(body: CartAddRequest, session: AgentSession = Depends(get_session)):
    if not session.state.products_approved:
        session.orchestrator.approve_products(True)
    return await cart_add(body, session)


@app.post("/api/cart/add-stream")
async def cart_add_stream(
    body: CartAddRequest,
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    """Stream per-item progress while adding to Woolworths cart."""
    resolved = session.state.resolved_list
    if not resolved:
        raise HTTPException(status_code=400, detail="No shop list")

    if body.export_only:
        return await cart_add(body, session)

    if not session.state.products_approved:
        session.orchestrator.approve_products(True)

    orch = session.orchestrator
    addable, _ = merge_line_items_by_sku(resolved.addable_items())
    total = len(addable)
    ww_user = _woolworths_user_id(session, user)

    async def stream():
        queue: asyncio.Queue = asyncio.Queue()

        async def on_progress(status: str, item, message: str = "") -> None:
            await queue.put(
                {
                    "type": "progress",
                    "ingredient": item.ingredient,
                    "product_name": item.product_name,
                    "status": status,
                    "message": message,
                }
            )

        async def run_cart() -> None:
            try:
                with woolworths_session_context(ww_user):
                    result = await orch.add_to_cart(
                        resolved,
                        plan_approved=session.state.plan_approved,
                        products_approved=True,
                        allow_over_budget=body.allow_over_budget,
                        on_progress=on_progress,
                    )
                await queue.put({"type": "done", "result": result})
            except ValueError as exc:
                await queue.put({"type": "error", "message": str(exc)})

        yield _sse_event("status", {"message": "Adding to cart…", "total": total, "done": 0})
        task = asyncio.create_task(run_cart())
        done_count = 0

        while True:
            item = await queue.get()
            if item["type"] == "error":
                yield _sse_event("error", {"message": item["message"]})
                break
            if item["type"] == "progress":
                if item["status"] in ("success", "failed", "skipped"):
                    done_count += 1
                yield _sse_event(
                    "progress",
                    {
                        **item,
                        "done": done_count,
                        "total": total,
                    },
                )
                continue
            if item["type"] == "done":
                result = item["result"]
                session.last_cart_result = result
                session.state.advance_to(AgentPhase.COMPLETE)
                yield _sse_event(
                    "complete",
                    {
                        "result": cart_result_out(
                            result, session.state.export_paths
                        ).model_dump(mode="json"),
                    },
                )
                break

        await task

    return _sse_response(stream())


@app.post("/api/cart/retry", response_model=CartResultOut)
async def cart_retry(
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    from woolworths_adapter.cart_retry import retry_cart_from_csv

    paths = session.state.export_paths
    csv_path = next((p for p in paths if p.endswith(".csv")), None)
    if not csv_path and session.state.resolved_list:
        paths = await session.orchestrator.export_only(session.state.resolved_list)
        csv_path = next((p for p in paths if p.endswith(".csv")), None)
    if not csv_path or not Path(csv_path).exists():
        raise HTTPException(status_code=400, detail="No export CSV available for retry")

    with woolworths_session_context(_woolworths_user_id(session, user)):
        result = await retry_cart_from_csv(csv_path, adapter=session.orchestrator.adapter)
    return cart_result_out(result, session.state.export_paths)


# --- Export ---


@app.get("/api/export/csv")
async def export_csv(session: AgentSession = Depends(get_session)):
    if not session.state.resolved_list:
        raise HTTPException(status_code=400, detail="No shop list")
    paths = await session.orchestrator.export_only(session.state.resolved_list)
    csv_path = next(p for p in paths if p.endswith(".csv"))
    return FileResponse(csv_path, filename=Path(csv_path).name, media_type="text/csv")


@app.get("/api/export/markdown")
async def export_markdown(session: AgentSession = Depends(get_session)):
    if not session.state.resolved_list:
        raise HTTPException(status_code=400, detail="No shop list")
    paths = await session.orchestrator.export_only(session.state.resolved_list)
    md_path = next(p for p in paths if p.endswith(".md"))
    return FileResponse(md_path, filename=Path(md_path).name, media_type="text/markdown")


@app.post("/api/cart/clear")
async def cart_clear(
    session: AgentSession = Depends(get_session),
    user=Depends(get_optional_user),
):
    """Empty the Woolworths trolley for the current Woolworths session."""
    from woolworths_adapter.client import WoolworthsError

    ww_user = _woolworths_user_id(session, user)
    try:
        with woolworths_session_context(ww_user):
            result = await session.orchestrator.adapter.clear_cart()
            remaining = await session.orchestrator.adapter.get_cart_skus()
    except WoolworthsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "cleared": len(remaining) == 0,
        "remaining_sku_count": len(remaining),
        "message": (result or {}).get("message", "Cart cleared"),
    }


@app.get("/api/cart/url")
async def cart_url():
    return {"url": WOOLWORTHS_CART_URL, "url_alt": WOOLWORTHS_CART_URL_FALLBACK}


def run() -> None:
    import uvicorn

    project_root = Path(__file__).resolve().parents[4]
    load_dotenv(project_root / ".env", override=True)
    # Auto-reload hangs on Windows after the first file change (uvicorn/WatchFiles).
    default_reload = "0" if sys.platform == "win32" else "1"
    reload_enabled = os.getenv("MEAL_AGENT_RELOAD", default_reload) == "1"

    host = "0.0.0.0"
    port = int(os.getenv("PORT", "8000"))

    if reload_enabled:
        uvicorn.run(
            "meal_agent_api.main:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=[
                str(project_root / "apps" / "api" / "src"),
                str(project_root / "packages"),
            ],
            reload_excludes=[
                "**/__pycache__/**",
                "**/data/**",
                "**/profiles/**",
                "**/exports/**",
                "**/.git/**",
                "**/node_modules/**",
                "**/apps/web/**",
            ],
            reload_delay=0.5,
        )
        return

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
