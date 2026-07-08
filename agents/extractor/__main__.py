"""A2A server for the Extractor agent.  Run: python -m agents.extractor"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import uvicorn

from a2a_lib.models import AgentCard, AgentSkill
from a2a_lib.server import create_agent_app
from agents.extractor.agent import ExtractorAgent
from common.config import settings

CARD = AgentCard(
    name="claims-extractor",
    description="Extracts structured claim fields (claimant, policy number, date, "
    "amount, incident type) from raw claim documents using a local LLM.",
    url=settings.extractor_url,
    skills=[
        AgentSkill(
            id="extract_claim",
            name="Extract claim fields",
            description="Input: {'text': <claim document>}. Output: ExtractedClaim JSON.",
            tags=["insurance", "extraction", "nlp"],
        )
    ],
)

agent = ExtractorAgent()


def handle(payload: dict) -> dict:
    text = payload.get("text", "")
    if not text:
        raise ValueError("payload must contain 'text' with the claim document")
    return agent.extract(text).model_dump()


app = create_agent_app(CARD, handle)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.agent_host, port=settings.extractor_port)
