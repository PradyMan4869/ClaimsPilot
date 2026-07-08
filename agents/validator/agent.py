"""Agent 2 — Validator.

Single responsibility: `ExtractedClaim` → `ValidationResult`.
Policy data comes from MongoDB via the MCP policy server; coverage rules are a
deterministic engine; CrewAI (when enabled) coordinates the two sub-tasks and
writes the reasoning narrative.
"""
from __future__ import annotations

from langsmith import traceable

from agents.validator.crew import build_reasoning_with_crew
from agents.validator.mcp_client import PolicyMCPClient
from agents.validator.rules import decide, run_rule_checks
from common.schemas import ExtractedClaim, RuleCheck, ValidationResult


class ValidatorAgent:
    def __init__(self, policy_client: PolicyMCPClient | None = None):
        self.policies = policy_client or PolicyMCPClient()

    @traceable(name="validator.validate", run_type="chain")
    def validate(self, claim: ExtractedClaim) -> ValidationResult:
        policy = self.policies.get_policy(claim.policy_number)
        checks = run_rule_checks(claim, policy)
        decision = decide(claim, checks)

        reasoning = build_reasoning_with_crew(claim, policy, checks, decision)
        if reasoning is None:
            reasoning = self._deterministic_reasoning(claim, checks, decision)

        return ValidationResult(
            policy_number=claim.policy_number,
            policy_found=policy is not None,
            decision=decision,
            checks=checks,
            reasoning=reasoning,
            claim=claim,
        )

    @staticmethod
    def _deterministic_reasoning(claim: ExtractedClaim, checks: list[RuleCheck], decision: str) -> str:
        failed = [c for c in checks if not c.passed]
        if decision == "reject":
            reasons = "; ".join(f"{c.rule}: {c.detail}" for c in failed)
            return f"Claim rejected — failed rule(s): {reasons}"
        if decision == "escalate":
            causes = []
            if claim.missing_fields:
                causes.append(f"missing fields {claim.missing_fields}")
            if claim.extraction_confidence < 0.6:
                causes.append(f"low extraction confidence ({claim.extraction_confidence:.2f})")
            causes.append(f"claim amount {claim.claim_amount:,.0f} vs auto-approve authority")
            return (
                "All coverage rules passed but the claim requires human review: "
                + "; ".join(causes) + "."
            )
        return (
            f"All {len(checks)} coverage rules passed and the amount "
            f"({claim.claim_amount:,.0f}) is within auto-approve authority."
        )
