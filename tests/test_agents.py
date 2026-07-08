"""Agent logic with the LLM mocked — pipeline behaviour must hold offline."""
from unittest.mock import MagicMock

from agents.extractor.agent import ExtractorAgent
from agents.responder.agent import ResponderAgent
from agents.validator.agent import ValidatorAgent
from common.schemas import ValidationResult

SAMPLE_DOC = """\
INSURANCE CLAIM SUBMISSION
==========================
Claimant Name: Aarav Sharma
Policy Number: POL-1000
Incident Date: 2024-06-15
Incident Type: accident
Claim Amount: $5,000.00

STATEMENT OF LOSS
-----------------
My vehicle was struck at a junction.
"""


def test_extractor_llm_path():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "claimant_name": "Aarav Sharma",
        "policy_number": "pol-1000",
        "incident_date": "2024-06-15",
        "incident_type": "Accident",
        "claim_amount": "5,000.00",
        "description": "Collision at a junction.",
    }
    claim = ExtractorAgent(llm).extract(SAMPLE_DOC)
    assert claim.policy_number == "POL-1000"  # normalised to upper
    assert claim.incident_type == "accident"  # normalised to lower
    assert claim.claim_amount == 5000.0
    assert claim.extraction_confidence == 0.9
    assert claim.missing_fields == []


def test_extractor_regex_fallback_when_llm_offline():
    llm = MagicMock()
    llm.complete_json.return_value = None
    claim = ExtractorAgent(llm).extract(SAMPLE_DOC)
    assert claim.policy_number == "POL-1000"
    assert claim.claim_amount == 5000.0
    assert claim.extraction_confidence <= 0.5  # marked uncertain → validator escalates


def test_validator_end_to_end_against_memory_store(valid_claim):
    policy_client = MagicMock()
    policy_client.get_policy.return_value = {
        "policy_number": "POL-1000", "holder_name": "Aarav Sharma", "status": "active",
        "coverage_start": "2023-01-01", "coverage_end": "2026-12-31",
        "coverage_limit": 50000, "covered_incident_types": ["accident"],
        "waiting_period_days": 30,
    }
    result = ValidatorAgent(policy_client).validate(valid_claim)
    assert result.decision == "approve"
    assert result.policy_found
    assert result.reasoning


def test_responder_template_fallback(valid_claim):
    llm = MagicMock()
    llm.complete.return_value = None
    validation = ValidationResult(
        policy_number="POL-1000", policy_found=True, decision="reject",
        checks=[], reasoning="failed", claim=valid_claim,
    )
    letter = ResponderAgent(llm).draft(validation)
    assert letter.decision == "reject"
    assert "Aarav Sharma" in letter.letter
    assert "appeal" in letter.letter
    assert any("Final decision: REJECT" in step for step in letter.reasoning_chain)
