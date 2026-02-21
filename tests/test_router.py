from __future__ import annotations

from pydantic import TypeAdapter

from src.agent.router import AgentRouter
from src.agent.schema import Intent
from src.agent.session_store import InMemorySessionStore, PendingTransfer


class MockGeminiClient:
    def __init__(self, first_output: str, repair_output: str | None = None) -> None:
        self.first_output = first_output
        self.repair_output = repair_output or first_output

    def generate_intent(self, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        return self.first_output

    def repair_intent(self, invalid_output: str, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        return self.repair_output


def test_schema_validation_transfer_draft() -> None:
    adapter = TypeAdapter(Intent)
    parsed = adapter.validate_python(
        {
            "intent": "TRANSFER_DRAFT",
            "payee_label": "James (Son)",
            "amount": 20.0,
            "currency": "EUR",
            "assistant_say": "Drafted.",
        }
    )
    assert parsed.intent == "TRANSFER_DRAFT"


def test_missing_payee_or_amount_returns_clarify() -> None:
    store = InMemorySessionStore()
    gemini = MockGeminiClient('{"intent":"CLARIFY","assistant_say":"Who should I pay and how much?","choices":null}')
    router = AgentRouter(store, gemini)

    response = router.handle_turn("s1", "send money")
    assert response.intent.intent == "CLARIFY"


def test_confirm_flow_with_pending_transfer_highlight_send() -> None:
    store = InMemorySessionStore()
    session = store.get("s2")
    session.pending_transfer = PendingTransfer(payee_label="James (Son)", amount=20.0, currency="EUR")
    gemini = MockGeminiClient('{"intent":"HELP","assistant_say":"unused"}')
    router = AgentRouter(store, gemini)

    response = router.handle_turn("s2", "confirm")
    assert response.intent.intent == "CONFIRM"
    assert response.ui_action is not None
    assert response.ui_action.type == "HIGHLIGHT_SEND"
    assert response.assistant_say == "Review and press Send."


def test_cancel_clears_pending_transfer_and_go_home() -> None:
    store = InMemorySessionStore()
    session = store.get("s3")
    session.pending_transfer = PendingTransfer(payee_label="Pete (Doctor)", amount=12.0, currency="EUR")
    gemini = MockGeminiClient('{"intent":"HELP","assistant_say":"unused"}')
    router = AgentRouter(store, gemini)

    response = router.handle_turn("s3", "cancel")
    assert response.intent.intent == "CANCEL"
    assert response.ui_action is not None
    assert response.ui_action.type == "GO_HOME"
    assert store.get("s3").pending_transfer is None
