"""CrewAI crew used *inside* the Validator agent.

Two sequential sub-tasks — policy lookup and rules evaluation — each backed by a
tool that wraps the deterministic layer (MCP policy lookup, rules engine). CrewAI
coordinates the sub-tasks and writes the reasoning narrative; it never overrides
the rule verdicts.

This module imports CrewAI lazily so the rest of the agent works when CrewAI is
disabled (CREWAI_ENABLED=false) or not installed.
"""
from __future__ import annotations

import json
import logging

from common.config import settings
from common.schemas import ExtractedClaim, RuleCheck
from agents.validator.mcp_client import PolicyMCPClient
from agents.validator.rules import run_rule_checks

logger = logging.getLogger(__name__)


def build_reasoning_with_crew(
    claim: ExtractedClaim, policy: dict | None, checks: list[RuleCheck], decision: str
) -> str | None:
    """Run the CrewAI crew; return its narrative, or None on any failure."""
    if not settings.crewai_enabled:
        return None
    try:
        from crewai import Agent, Crew, LLM, Process, Task
        from crewai.tools import tool
    except ImportError:
        logger.warning("CrewAI not installed — using deterministic reasoning")
        return None

    llm = LLM(
        model=f"openai/{settings.lmstudio_model}",
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
    )

    mcp_client = PolicyMCPClient()

    @tool("policy_lookup")
    def policy_lookup(policy_number: str) -> str:
        """Fetch the policy record for a policy number via the MCP policy server."""
        record = mcp_client.get_policy(policy_number)
        return json.dumps(record) if record else "POLICY NOT FOUND"

    @tool("rules_engine")
    def rules_engine(unused: str = "") -> str:
        """Return the deterministic rule-check results for the claim under review."""
        return json.dumps([c.model_dump() for c in checks])

    policy_analyst = Agent(
        role="Policy Analyst",
        goal="Retrieve and summarise the policy relevant to the claim",
        backstory="You verify coverage details for an insurance claims department.",
        tools=[policy_lookup],
        llm=llm,
        verbose=False,
    )
    rules_reviewer = Agent(
        role="Coverage Rules Reviewer",
        goal="Explain the rule-check outcomes and justify the coverage decision",
        backstory="You document claim validation reasoning for audit purposes.",
        tools=[rules_engine],
        llm=llm,
        verbose=False,
    )

    lookup_task = Task(
        description=f"Look up policy {claim.policy_number} and summarise its coverage terms.",
        expected_output="A short summary of the policy's status, window, limit and covered types.",
        agent=policy_analyst,
    )
    review_task = Task(
        description=(
            f"The claim: {claim.model_dump_json()}. The engine decided: {decision}. "
            "Fetch the rule-check results and write a 3-5 sentence audit reasoning "
            "explaining the decision strictly from those results."
        ),
        expected_output="A concise reasoning paragraph referencing each failed or decisive rule.",
        agent=rules_reviewer,
        context=[lookup_task],
    )

    try:
        crew = Crew(
            agents=[policy_analyst, rules_reviewer],
            tasks=[lookup_task, review_task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        return str(result)
    except Exception as exc:
        logger.warning("CrewAI run failed (%s) — using deterministic reasoning", exc)
        return None
