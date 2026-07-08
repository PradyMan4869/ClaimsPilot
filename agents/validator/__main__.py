"""A2A server for the Validator agent.  Run: python -m agents.validator"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import uvicorn

from a2a_lib.models import AgentCard, AgentSkill
from a2a_lib.server import create_agent_app
from agents.validator.agent import ValidatorAgent
from common.config import settings
from common.schemas import ExtractedClaim

CARD = AgentCard(
    name="claims-validator",
    description="Validates extracted claims against policy records (MongoDB via MCP) "
    "and a deterministic coverage rules engine; CrewAI coordinates the sub-tasks.",
    url=settings.validator_url,
    skills=[
        AgentSkill(
            id="validate_claim",
            name="Validate claim coverage",
            description="Input: ExtractedClaim JSON. Output: ValidationResult JSON "
            "(decision: approve | reject | escalate, with per-rule checks).",
            tags=["insurance", "validation", "rules", "crewai", "mcp"],
        )
    ],
)

agent = ValidatorAgent()


def handle(payload: dict) -> dict:
    claim = ExtractedClaim.model_validate(payload)
    return agent.validate(claim).model_dump()


app = create_agent_app(CARD, handle)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.agent_host, port=settings.validator_port)
