from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter, ValidationError

from src.agent.gemini_client import GeminiClient
from src.agent.schema import (
    AgentTurnResponse,
    CancelIntent,
    ClarifyIntent,
    ConfirmIntent,
    Intent,
    OpenBalanceAction,
    OpenTransferAction,
    UIAction,
    GoHomeAction,
    HighlightSendAction,
    TransferDraftIntent,
)
from src.agent.session_store import FAKE_BALANCE, InMemorySessionStore, PendingTransfer


INTENT_ADAPTER = TypeAdapter(Intent)


def map_intent_to_ui_action(intent: Intent, pending_exists: bool) -> UIAction | None:
    if intent.intent == "CANCEL":
        return GoHomeAction(type="GO_HOME")
    if intent.intent == "CHECK_BALANCE":
        return OpenBalanceAction(type="OPEN_BALANCE")
    if intent.intent == "TRANSFER_DRAFT":
        transfer = TransferDraftIntent.model_validate(intent)
        return OpenTransferAction(
            type="OPEN_TRANSFER",
            payee_label=transfer.payee_label,
            amount=transfer.amount,
            currency=transfer.currency,
        )
    if intent.intent == "CONFIRM" and pending_exists:
        return HighlightSendAction(type="HIGHLIGHT_SEND")
    return None


class AgentRouter:
    def __init__(self, session_store: InMemorySessionStore, gemini_client: GeminiClient) -> None:
        self.session_store = session_store
        self.gemini_client = gemini_client

    def handle_turn(self, session_id: str, transcript: str) -> AgentTurnResponse:
        session = self.session_store.get(session_id)

        forced = self._force_intent_if_keyword(transcript, session.pending_transfer is not None)
        debug: dict[str, Any] = {"forced": forced is not None}

        if forced is not None:
            intent = forced
        else:
            intent, model_debug = self._intent_from_llm(transcript, session)
            debug.update(model_debug)

        intent = self._normalize_intent(intent, session.payees_allowed, session.pending_transfer is not None)

        if intent.intent == "TRANSFER_DRAFT":
            transfer = TransferDraftIntent.model_validate(intent)
            session.pending_transfer = PendingTransfer(
                payee_label=transfer.payee_label,
                amount=transfer.amount,
                currency=transfer.currency,
            )
            session.screen = "transfer"
        elif intent.intent == "CANCEL":
            session.pending_transfer = None
            session.screen = "home"
        elif intent.intent == "CHECK_BALANCE":
            session.screen = "balance"
        elif intent.intent == "CONFIRM" and session.pending_transfer is not None:
            session.screen = "transfer"

        ui_action = map_intent_to_ui_action(intent, pending_exists=session.pending_transfer is not None)
        return AgentTurnResponse(
            assistant_say=intent.assistant_say,
            intent=intent,
            ui_action=ui_action,
            debug=debug,
        )

    def _force_intent_if_keyword(self, transcript: str, has_pending: bool) -> Intent | None:
        text = transcript.lower().strip()
        cancel_words = ("cancel", "stop", "never mind", "nevermind")
        confirm_words = ("confirm", "yes", "send it", "do it")

        if any(word in text for word in cancel_words):
            return CancelIntent(intent="CANCEL", assistant_say="Okay, canceled and back to home.")

        if any(word in text for word in confirm_words):
            if has_pending:
                return ConfirmIntent(intent="CONFIRM", assistant_say="Review and press Send.")
            return ClarifyIntent(
                intent="CLARIFY",
                assistant_say="I don't have a draft transfer yet. Who would you like to pay and how much?",
                choices=None,
            )

        return None

    def _intent_from_llm(self, transcript: str, session: Any) -> tuple[Intent, dict[str, Any]]:
        debug: dict[str, Any] = {"repair_attempted": False}
        pending_dict = (
            None
            if session.pending_transfer is None
            else {
                "payee_label": session.pending_transfer.payee_label,
                "amount": session.pending_transfer.amount,
                "currency": session.pending_transfer.currency,
            }
        )

        try:
            raw = self.gemini_client.generate_intent(transcript, session.payees_allowed, pending_dict)
            parsed = INTENT_ADAPTER.validate_python(json.loads(raw))
            debug["raw"] = raw
            return parsed, debug
        except (ValidationError, ValueError, json.JSONDecodeError) as first_error:
            debug["repair_attempted"] = True
            debug["first_error"] = str(first_error)
            invalid_output = debug.get("raw", "") or str(first_error)
            try:
                repaired = self.gemini_client.repair_intent(
                    invalid_output=invalid_output,
                    transcript=transcript,
                    payees_allowed=session.payees_allowed,
                    pending_transfer=pending_dict,
                )
                parsed = INTENT_ADAPTER.validate_python(json.loads(repaired))
                debug["repaired_raw"] = repaired
                return parsed, debug
            except (ValidationError, ValueError, json.JSONDecodeError) as repair_error:
                debug["repair_error"] = str(repair_error)
                return (
                    ClarifyIntent(
                        intent="CLARIFY",
                        assistant_say="Sorry—could you repeat that?",
                        choices=None,
                    ),
                    debug,
                )

    def _normalize_intent(self, intent: Intent, payees_allowed: list[str], has_pending: bool) -> Intent:
        if intent.intent == "TRANSFER_DRAFT":
            transfer = TransferDraftIntent.model_validate(intent)
            if transfer.payee_label not in payees_allowed:
                lowered = transfer.payee_label.lower()
                candidates = [p for p in payees_allowed if lowered in p.lower() or p.lower() in lowered]
                return ClarifyIntent(
                    intent="CLARIFY",
                    assistant_say="Which payee did you mean?",
                    choices=candidates or payees_allowed,
                )
            if transfer.amount <= 0 or transfer.amount > 10000:
                return ClarifyIntent(
                    intent="CLARIFY",
                    assistant_say="What amount should I draft? Please use an amount between 0 and 10000 EUR.",
                    choices=None,
                )

        if intent.intent == "CONFIRM" and not has_pending:
            return ClarifyIntent(
                intent="CLARIFY",
                assistant_say="I don't have a draft transfer yet. Who would you like to pay and how much?",
                choices=None,
            )

        if intent.intent == "CHECK_BALANCE":
            return INTENT_ADAPTER.validate_python(
                {
                    "intent": "CHECK_BALANCE",
                    "assistant_say": f"Your balance is {FAKE_BALANCE:.2f} EUR.",
                }
            )

        return intent
