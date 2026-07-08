"""Agent 1 — Extractor.

Single responsibility: claim document text → structured `ExtractedClaim`.
LLM does the reading; a regex fallback keeps the pipeline alive when LM Studio
is offline (with confidence marked low so the Validator can escalate).
"""
from __future__ import annotations

import re

from langsmith import traceable

from common.llm import LocalLLM
from common.schemas import ExtractedClaim

SYSTEM_PROMPT = """\
You are a claims intake specialist. Extract structured fields from the insurance
claim document. Fields:
- claimant_name (string)
- policy_number (string, format POL-XXXX)
- incident_date (ISO date YYYY-MM-DD)
- incident_type (one of: accident, theft, fire, flood, other)
- claim_amount (number, no currency symbols)
- description (one-sentence summary of the incident)
Use "unknown" (or 0 for claim_amount) when a field is genuinely absent.
"""

REQUIRED_FIELDS = ["claimant_name", "policy_number", "incident_date", "incident_type", "claim_amount"]


class ExtractorAgent:
    def __init__(self, llm: LocalLLM | None = None):
        self.llm = llm or LocalLLM()

    @traceable(name="extractor.extract", run_type="chain")
    def extract(self, document_text: str) -> ExtractedClaim:
        data = self.llm.complete_json(SYSTEM_PROMPT, document_text[:6000])
        if data is not None:
            claim = self._to_claim(data, confidence=0.9)
        else:
            claim = self._regex_fallback(document_text)

        claim.missing_fields = [
            f for f in REQUIRED_FIELDS
            if str(getattr(claim, f)) in ("unknown", "0", "0.0")
        ]
        if claim.missing_fields:
            claim.extraction_confidence = min(claim.extraction_confidence, 0.5)
        return claim

    @staticmethod
    def _to_claim(data: dict, confidence: float) -> ExtractedClaim:
        try:
            amount = float(str(data.get("claim_amount", 0)).replace(",", "").replace("$", ""))
        except ValueError:
            amount = 0.0
        return ExtractedClaim(
            claimant_name=str(data.get("claimant_name") or "unknown"),
            policy_number=str(data.get("policy_number") or "unknown").upper(),
            incident_date=str(data.get("incident_date") or "unknown"),
            incident_type=str(data.get("incident_type") or "unknown").lower(),
            claim_amount=amount,
            description=str(data.get("description") or ""),
            extraction_confidence=confidence,
        )

    @staticmethod
    def _regex_fallback(text: str) -> ExtractedClaim:
        """Deterministic extraction for the structured header our synthetic docs carry."""
        def find(pattern: str) -> str | None:
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1).strip() if match else None

        amount_raw = find(r"(?:claim amount|amount claimed)[:\s]*[$₹]?\s*([\d,]+(?:\.\d+)?)")
        return ExtractorAgent._to_claim(
            {
                "claimant_name": find(r"claimant(?: name)?[:\s]+(.+)"),
                "policy_number": find(r"policy(?: number| no\.?)?[:\s]+(POL-\d+)"),
                "incident_date": find(r"(?:incident |loss )?date[:\s]+(\d{4}-\d{2}-\d{2})"),
                "incident_type": find(r"incident type[:\s]+(\w+)"),
                "claim_amount": amount_raw.replace(",", "") if amount_raw else 0,
                "description": "Extracted via fallback parser (LLM unavailable).",
            },
            confidence=0.4,
        )
