"""Agent 3 — Responder.

Single responsibility: `ValidationResult` → `ResponseLetter`.
Drafts the accept/reject/escalate letter with the full reasoning chain; a
template fallback guarantees a letter even with LM Studio offline.
"""
from __future__ import annotations

from langsmith import traceable

from common.llm import LocalLLM
from common.schemas import ResponseLetter, ValidationResult

SYSTEM_PROMPT = """\
You are a claims correspondence specialist at an insurance company. Draft a formal
letter to the claimant communicating the outcome of their claim.

Rules:
- Address the claimant by name; reference the policy number and incident date.
- Decision 'approve': confirm approval, state the amount, note the deductible applies.
- Decision 'reject': state the rejection, cite each failed rule plainly, and mention
  the right to appeal within 30 days.
- Decision 'escalate': explain the claim passed initial checks and is under review by
  a senior adjuster, with a response expected within 5 business days.
- Professional, plain English, no markdown, 120-220 words, sign as "ClaimsPilot
  Automated Claims Desk".
"""


class ResponderAgent:
    def __init__(self, llm: LocalLLM | None = None):
        self.llm = llm or LocalLLM()

    @traceable(name="responder.draft", run_type="chain")
    def draft(self, validation: ValidationResult) -> ResponseLetter:
        chain = self._reasoning_chain(validation)
        letter = self.llm.complete(
            SYSTEM_PROMPT,
            "Validation result:\n" + validation.model_dump_json(indent=2),
            temperature=0.4,
        )
        if not letter:
            letter = self._template_letter(validation)
        return ResponseLetter(decision=validation.decision, letter=letter, reasoning_chain=chain)

    @staticmethod
    def _reasoning_chain(validation: ValidationResult) -> list[str]:
        chain = [
            f"Extraction: claim by {validation.claim.claimant_name} on policy "
            f"{validation.policy_number}, {validation.claim.incident_type} on "
            f"{validation.claim.incident_date}, amount {validation.claim.claim_amount:,.0f} "
            f"(confidence {validation.claim.extraction_confidence:.2f})",
        ]
        chain += [f"Rule {c.rule}: {'PASS' if c.passed else 'FAIL'} — {c.detail}" for c in validation.checks]
        chain.append(f"Validator reasoning: {validation.reasoning}")
        chain.append(f"Final decision: {validation.decision.upper()}")
        return chain

    @staticmethod
    def _template_letter(validation: ValidationResult) -> str:
        claim = validation.claim
        header = (
            f"Dear {claim.claimant_name},\n\n"
            f"Re: Claim under policy {validation.policy_number} "
            f"(incident dated {claim.incident_date}).\n\n"
        )
        footer = "\n\nSincerely,\nClaimsPilot Automated Claims Desk"
        if validation.decision == "approve":
            body = (
                f"We are pleased to confirm that your claim for {claim.claim_amount:,.0f} "
                "has been approved. Payment will be processed shortly; your policy "
                "deductible applies."
            )
        elif validation.decision == "reject":
            failed = "; ".join(c.detail for c in validation.checks if not c.passed)
            body = (
                "After review, we are unable to approve your claim for the following "
                f"reason(s): {failed} You may appeal this decision within 30 days."
            )
        else:
            body = (
                "Your claim has passed initial verification and has been referred to a "
                "senior claims adjuster for review. You can expect a response within "
                "5 business days."
            )
        return header + body + footer
