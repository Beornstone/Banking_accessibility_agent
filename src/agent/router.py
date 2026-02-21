from __future__ import annotations

import json
import re
from dataclasses import asdict

from pydantic import TypeAdapter, ValidationError

from src.agent.gemini_client import LLMClient
from src.agent.schema import (
    AgentTurnResponse,
    CancelIntent,
    ClarifyIntent,
    ConfirmIntent,
    Intent,
    OpenBalanceAction,
    OpenTransferAction,
    UIAction,
    HighlightSendAction,
    GoHomeAction,
)
from src.agent.session_store import FAKE_BALANCE_EUR, InMemorySessionStore

intent_adapter = TypeAdapter(Intent)


def map_intent_to_ui_action(intent: Intent, pending_exists: bool) -> UIAction | None:
    if intent.intent == "CANCEL":
        return GoHomeAction(type="GO_HOME")
    if intent.intent == "CHECK_BALANCE":
        return OpenBalanceAction(type="OPEN_BALANCE")
    if intent.intent == "TRANSFER_DRAFT":
        return OpenTransferAction(
            type="OPEN_TRANSFER",
            payee_label=intent.payee_label,
            amount=intent.amount,
            currency=intent.currency,
        )
    if intent.intent == "CONFIRM" and pending_exists:
        return HighlightSendAction(type="HIGHLIGHT_SEND")
    return None


class AgentRouter:
    def __init__(self, llm_client: LLMClient, session_store: InMemorySessionStore) -> None:
        self.llm_client = llm_client
        self.session_store = session_store

    def handle_turn(self, session_id: str, transcript: str) -> AgentTurnResponse:
        state = self.session_store.get(session_id)
        t = transcript.strip().lower()
        if re.search(r"\b(cancel|stop|never mind|nevermind)\b", t):
            self.session_store.clear_pending_transfer(session_id)
            state.screen = "home"
            intent = CancelIntent(intent="CANCEL", assistant_say="Okay, cancelled. Back to home.")
            return AgentTurnResponse(
                assistant_say=intent.assistant_say,
                intent=intent,
                ui_action=map_intent_to_ui_action(intent, pending_exists=False),
                debug=None,
            )

        pending_payload = asdict(state.pending_transfer) if state.pending_transfer else None
        raw = self.llm_client.complete_json(
            transcript=transcript,
            payees_allowed=state.payees_allowed,
            pending_transfer=pending_payload,
        )
        intent, debug = self._parse_or_repair(raw, transcript, state.payees_allowed, pending_payload)

        if intent.intent == "TRANSFER_DRAFT" and intent.payee_label not in state.payees_allowed:
            intent = ClarifyIntent(
                intent="CLARIFY",
                assistant_say="I found multiple matches. Which payee did you mean?",
                choices=state.payees_allowed,
            )

        if intent.intent == "CONFIRM" and not state.pending_transfer:
            intent = ClarifyIntent(intent="CLARIFY", assistant_say="There is no pending transfer to confirm.", choices=None)

        if intent.intent == "CHECK_BALANCE":
            intent.assistant_say = f"Your balance is {FAKE_BALANCE_EUR:.2f} EUR."

        if intent.intent == "TRANSFER_DRAFT":
            self.session_store.set_pending_transfer(session_id, intent.payee_label, intent.amount)
            state.screen = "transfer"
        elif intent.intent == "CANCEL":
            self.session_store.clear_pending_transfer(session_id)
            state.screen = "home"
        elif intent.intent == "CHECK_BALANCE":
            state.screen = "balance"
        elif intent.intent == "CONFIRM":
            intent = ConfirmIntent(intent="CONFIRM", assistant_say="Review and press Send")

        ui_action = map_intent_to_ui_action(intent, pending_exists=state.pending_transfer is not None)
        return AgentTurnResponse(assistant_say=intent.assistant_say, intent=intent, ui_action=ui_action, debug=debug)

    def _parse_or_repair(
        self,
        raw_output: str,
        transcript: str,
        payees_allowed: list[str],
        pending_transfer: dict | None,
    ) -> tuple[Intent, dict | None]:
        parsed = self._validate_from_raw(raw_output)
        if parsed is not None:
            return parsed, {"model_raw": raw_output}

        repaired_raw = self.llm_client.repair_json(
            invalid_output=raw_output,
            transcript=transcript,
            payees_allowed=payees_allowed,
            pending_transfer=pending_transfer,
        )
        repaired = self._validate_from_raw(repaired_raw)
        if repaired is not None:
            return repaired, {"model_raw": raw_output, "repair_raw": repaired_raw}

        fallback = ClarifyIntent(intent="CLARIFY", assistant_say="Sorry—could you repeat that?", choices=None)
        return fallback, {"model_raw": raw_output, "repair_raw": repaired_raw, "fallback": True}

    def _validate_from_raw(self, raw_output: str) -> Intent | None:
        if not raw_output:
            return None
        json_text = _extract_first_json_object(raw_output)
        if not json_text:
            return None
        try:
            payload = json.loads(json_text)
            intent = intent_adapter.validate_python(payload)
            return intent
        except (json.JSONDecodeError, ValidationError):
            return None


def _extract_first_json_object(raw: str) -> str | None:
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(raw)):
        ch = raw[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : idx + 1]
    return None
