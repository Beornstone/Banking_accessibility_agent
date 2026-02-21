from __future__ import annotations

from fastapi import FastAPI

from src.agent.gemini_client import GeminiClient
from src.agent.router import AgentRouter
from src.agent.schema import AgentTurnRequest, AgentTurnResponse
from src.agent.session_store import InMemorySessionStore

app = FastAPI(title="Voice Banking Agent Router")

session_store = InMemorySessionStore()
router = AgentRouter(session_store=session_store, gemini_client=GeminiClient())


@app.post("/agent/turn", response_model=AgentTurnResponse)
def agent_turn(payload: AgentTurnRequest) -> AgentTurnResponse:
    return router.handle_turn(payload.session_id, payload.transcript)
