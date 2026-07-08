"""Pydantic contracts exchanged between agents as A2A DataParts.

These schemas ARE the inter-agent API: Extractor emits `ExtractedClaim`,
Validator emits `ValidationResult`, Responder emits `ResponseLetter`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["approve", "reject", "escalate"]


class ExtractedClaim(BaseModel):
    claimant_name: str = "unknown"
    policy_number: str = "unknown"
    incident_date: str = "unknown"  # ISO date string when parseable
    incident_type: str = "unknown"
    claim_amount: float = 0.0
    description: str = ""
    extraction_confidence: float = Field(0.0, ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list)


class RuleCheck(BaseModel):
    rule: str
    passed: bool
    detail: str


class ValidationResult(BaseModel):
    policy_number: str
    policy_found: bool
    decision: Decision
    checks: list[RuleCheck] = Field(default_factory=list)
    reasoning: str = ""
    claim: ExtractedClaim


class ResponseLetter(BaseModel):
    decision: Decision
    letter: str
    reasoning_chain: list[str] = Field(default_factory=list)
