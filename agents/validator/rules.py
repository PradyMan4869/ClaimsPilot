"""Deterministic coverage rules engine.

Coverage decisions are code, not LLM output: the LLM (via CrewAI) narrates the
reasoning, but pass/fail on each rule is computed here and is unit-testable.
"""
from __future__ import annotations

from datetime import date, timedelta

from common.config import settings
from common.schemas import Decision, ExtractedClaim, RuleCheck


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def run_rule_checks(claim: ExtractedClaim, policy: dict | None) -> list[RuleCheck]:
    checks: list[RuleCheck] = []

    if policy is None:
        checks.append(RuleCheck(rule="policy_exists", passed=False,
                                detail=f"No policy found for {claim.policy_number}."))
        return checks
    checks.append(RuleCheck(rule="policy_exists", passed=True,
                            detail=f"Policy {policy['policy_number']} found for {policy['holder_name']}."))

    active = policy.get("status") == "active"
    checks.append(RuleCheck(rule="policy_active", passed=active,
                            detail=f"Policy status is '{policy.get('status')}'."))

    incident = _parse_date(claim.incident_date)
    start = _parse_date(policy.get("coverage_start", ""))
    end = _parse_date(policy.get("coverage_end", ""))
    if incident and start and end:
        in_window = start <= incident <= end
        checks.append(RuleCheck(rule="within_coverage_period", passed=in_window,
                                detail=f"Incident {incident} vs coverage {start}..{end}."))
        waiting_end = start + timedelta(days=int(policy.get("waiting_period_days", 0)))
        checks.append(RuleCheck(rule="waiting_period_elapsed", passed=incident >= waiting_end,
                                detail=f"Waiting period ends {waiting_end}."))
    else:
        checks.append(RuleCheck(rule="within_coverage_period", passed=False,
                                detail=f"Unparseable incident date '{claim.incident_date}'."))

    covered_types = [t.lower() for t in policy.get("covered_incident_types", [])]
    checks.append(RuleCheck(
        rule="incident_type_covered",
        passed=claim.incident_type in covered_types,
        detail=f"Incident type '{claim.incident_type}' vs covered {covered_types}.",
    ))

    limit = float(policy.get("coverage_limit", 0))
    checks.append(RuleCheck(
        rule="within_coverage_limit",
        passed=0 < claim.claim_amount <= limit,
        detail=f"Claim amount {claim.claim_amount:,.0f} vs limit {limit:,.0f}.",
    ))

    return checks


def decide(claim: ExtractedClaim, checks: list[RuleCheck]) -> Decision:
    if any(not c.passed for c in checks):
        return "reject"
    if claim.extraction_confidence < 0.6 or claim.missing_fields:
        return "escalate"  # rules pass but the data itself is uncertain
    if claim.claim_amount > settings.auto_approve_limit:
        return "escalate"  # above auto-approve authority — human review
    return "approve"
