from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class AgentTurnRequest(BaseModel):
    session_id: str
    transcript: str


class GoHomeAction(BaseModel):
    type: Literal["GO_HOME"]


class OpenBalanceAction(BaseModel):
    type: Literal["OPEN_BALANCE"]


class OpenTransferAction(BaseModel):
    type: Literal["OPEN_TRANSFER"]
    payee_label: str
    amount: float
    currency: Literal["EUR"] = "EUR"


class HighlightSendAction(BaseModel):
    type: Literal["HIGHLIGHT_SEND"]


UIAction = Annotated[
    GoHomeAction | OpenBalanceAction | OpenTransferAction | HighlightSendAction,
    Field(discriminator="type"),
]


class CheckBalanceIntent(BaseModel):
    intent: Literal["CHECK_BALANCE"]
    assistant_say: str


class TransferDraftIntent(BaseModel):
    intent: Literal["TRANSFER_DRAFT"]
    payee_label: str
    amount: float
    currency: Literal["EUR"] = "EUR"
    assistant_say: str

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        if value <= 0 or value > 10000:
            raise ValueError("amount must be between 0 and 10000")
        return value


class ConfirmIntent(BaseModel):
    intent: Literal["CONFIRM"]
    assistant_say: str


class CancelIntent(BaseModel):
    intent: Literal["CANCEL"]
    assistant_say: str


class ClarifyIntent(BaseModel):
    intent: Literal["CLARIFY"]
    assistant_say: str
    choices: list[str] | None = None


class HelpIntent(BaseModel):
    intent: Literal["HELP"]
    assistant_say: str


Intent = Annotated[
    CheckBalanceIntent
    | TransferDraftIntent
    | ConfirmIntent
    | CancelIntent
    | ClarifyIntent
    | HelpIntent,
    Field(discriminator="intent"),
]


class AgentTurnResponse(BaseModel):
    assistant_say: str
    intent: Intent
    ui_action: UIAction | None = None
    debug: dict | None = None
