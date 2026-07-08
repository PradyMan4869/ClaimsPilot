import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.schemas import ExtractedClaim


@pytest.fixture
def valid_claim() -> ExtractedClaim:
    """Clean claim against seeded active policy POL-1000 (limit 50k, accident covered)."""
    return ExtractedClaim(
        claimant_name="Aarav Sharma",
        policy_number="POL-1000",
        incident_date="2024-06-15",
        incident_type="accident",
        claim_amount=5000.0,
        description="Minor collision at a junction.",
        extraction_confidence=0.9,
    )


@pytest.fixture
def sample_policy() -> dict:
    return {
        "policy_number": "POL-1000",
        "holder_name": "Aarav Sharma",
        "status": "active",
        "coverage_start": "2023-01-01",
        "coverage_end": "2026-12-31",
        "coverage_limit": 50000,
        "deductible": 500,
        "covered_incident_types": ["accident", "theft", "fire"],
        "waiting_period_days": 30,
    }
