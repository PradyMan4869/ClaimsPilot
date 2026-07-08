"""A2A server for the Responder agent.  Run: python -m agents.responder"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import uvicorn

from a2a_lib.models import AgentCard, AgentSkill
from a2a_lib.server import create_agent_app
from agents.responder.agent import ResponderAgent
from common.config import settings
from common.schemas import ValidationResult

CARD = AgentCard(
    name="claims-responder",
    description="Drafts the accept/reject/escalate response letter from a validation "
    "result, preserving the full reasoning chain for audit.",
    url=settings.responder_url,
    skills=[
        AgentSkill(
            id="draft_response",
            name="Draft response letter",
            description="Input: ValidationResult JSON. Output: ResponseLetter JSON.",
            tags=["insurance", "correspondence", "llm"],
        )
    ],
)

agent = ResponderAgent()


def handle(payload: dict) -> dict:
    validation = ValidationResult.model_validate(payload)
    return agent.draft(validation).model_dump()


app = create_agent_app(CARD, handle)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.agent_host, port=settings.responder_port)
