from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Literal


DEFAULT_PAYEES = [
    "James (Son)",
    "Pete (Doctor)",
    "Sarah (Landlord)",
    "Aisha (Friend)",
]

FAKE_BALANCE = 1234.56


@dataclass
class PendingTransfer:
    payee_label: str
    amount: float
    currency: Literal["EUR"] = "EUR"


@dataclass
class SessionState:
    payees_allowed: list[str] = field(default_factory=lambda: DEFAULT_PAYEES.copy())
    pending_transfer: PendingTransfer | None = None
    screen: Literal["home", "transfer", "balance"] = "home"


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState()
            return self._sessions[session_id]

    def clear_pending_transfer(self, session_id: str) -> SessionState:
        session = self.get(session_id)
        session.pending_transfer = None
        return session
