from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from src.agent.gemini_client import GeminiClient
from src.agent.router import AgentRouter
from src.agent.schema import AgentTurnRequest, AgentTurnResponse
from src.agent.session_store import InMemorySessionStore

app = FastAPI(title="Voice Banking Agent Router")

session_store = InMemorySessionStore()
router = AgentRouter(llm_client=GeminiClient(), session_store=session_store)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/agent/turn", response_model=AgentTurnResponse)
def agent_turn(payload: AgentTurnRequest) -> AgentTurnResponse:
    return router.handle_turn(session_id=payload.session_id, transcript=payload.transcript)
