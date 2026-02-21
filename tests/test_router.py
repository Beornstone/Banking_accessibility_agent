from __future__ import annotations

import json

from src.agent.router import AgentRouter
from src.agent.schema import TransferDraftIntent
from src.agent.session_store import InMemorySessionStore


class MockGemini:
    def __init__(self, output: str, repair_output: str | None = None) -> None:
        self.output = output
        self.repair_output = repair_output or output

    def complete_json(self, **_: object) -> str:
        return self.output

    def repair_json(self, **_: object) -> str:
        return self.repair_output


def test_schema_validation_transfer_amount() -> None:
    intent = TransferDraftIntent(
        intent="TRANSFER_DRAFT",
        payee_label="James (Son)",
        amount=10,
        currency="EUR",
        assistant_say="Drafting",
    )
    assert intent.amount == 10


def test_missing_payee_or_amount_leads_to_clarify() -> None:
    llm = MockGemini(output=json.dumps({"intent": "CLARIFY", "assistant_say": "Who is the payee?", "choices": None}))
    router = AgentRouter(llm_client=llm, session_store=InMemorySessionStore())

    result = router.handle_turn(session_id="s1", transcript="send money")

    assert result.intent.intent == "CLARIFY"


def test_confirm_with_pending_transfer_highlights_send() -> None:
    llm = MockGemini(output=json.dumps({"intent": "CONFIRM", "assistant_say": "Confirming"}))
    store = InMemorySessionStore()
    store.set_pending_transfer("s2", "James (Son)", 20)
    router = AgentRouter(llm_client=llm, session_store=store)

    result = router.handle_turn(session_id="s2", transcript="confirm")

    assert result.intent.intent == "CONFIRM"
    assert result.assistant_say == "Review and press Send"
    assert result.ui_action is not None
    assert result.ui_action.type == "HIGHLIGHT_SEND"


def test_cancel_clears_pending_and_goes_home() -> None:
    llm = MockGemini(output=json.dumps({"intent": "HELP", "assistant_say": "help"}))
    store = InMemorySessionStore()
    store.set_pending_transfer("s3", "James (Son)", 30)
    router = AgentRouter(llm_client=llm, session_store=store)

    result = router.handle_turn(session_id="s3", transcript="cancel")

    assert result.intent.intent == "CANCEL"
    assert result.ui_action is not None
    assert result.ui_action.type == "GO_HOME"
    assert store.get("s3").pending_transfer is None
