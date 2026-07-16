"""In-memory session store — one orchestrator per browser session."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from threading import Lock

from agent.budget import BudgetSuggestion
from agent.orchestrator import CartResult, MealAgentOrchestrator
from shared.models import ConversationState


@dataclass
class AgentSession:
    id: str
    orchestrator: MealAgentOrchestrator
    user_id: str | None = None
    budget_suggestions: list[BudgetSuggestion] = field(default_factory=list)
    last_cart_result: CartResult | None = None
    export_only: bool = False

    @property
    def state(self) -> ConversationState:
        return self.orchestrator.state


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._lock = Lock()

    def create(self, *, user_id: str | None = None) -> AgentSession:
        session_id = str(uuid.uuid4())
        session = AgentSession(
            id=session_id,
            orchestrator=MealAgentOrchestrator(),
            user_id=user_id,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> AgentSession | None:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> AgentSession:
        session = self.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


store = SessionStore()
