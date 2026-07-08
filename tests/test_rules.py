from agents.validator.rules import decide, run_rule_checks


def _failed(checks):
    return {c.rule for c in checks if not c.passed}


def test_clean_claim_approves(valid_claim, sample_policy):
    checks = run_rule_checks(valid_claim, sample_policy)
    assert _failed(checks) == set()
    assert decide(valid_claim, checks) == "approve"


def test_unknown_policy_rejects(valid_claim):
    checks = run_rule_checks(valid_claim, None)
    assert decide(valid_claim, checks) == "reject"
    assert _failed(checks) == {"policy_exists"}


def test_lapsed_policy_rejects(valid_claim, sample_policy):
    sample_policy["status"] = "lapsed"
    checks = run_rule_checks(valid_claim, sample_policy)
    assert "policy_active" in _failed(checks)
    assert decide(valid_claim, checks) == "reject"


def test_uncovered_incident_type_rejects(valid_claim, sample_policy):
    valid_claim.incident_type = "flood"
    checks = run_rule_checks(valid_claim, sample_policy)
    assert "incident_type_covered" in _failed(checks)


def test_over_limit_rejects(valid_claim, sample_policy):
    valid_claim.claim_amount = 60000
    checks = run_rule_checks(valid_claim, sample_policy)
    assert "within_coverage_limit" in _failed(checks)


def test_waiting_period_rejects(valid_claim, sample_policy):
    valid_claim.incident_date = "2023-01-10"  # within 30-day waiting period
    checks = run_rule_checks(valid_claim, sample_policy)
    assert "waiting_period_elapsed" in _failed(checks)


def test_high_amount_escalates(valid_claim, sample_policy):
    valid_claim.claim_amount = 20000  # passes limit, exceeds AUTO_APPROVE_LIMIT=10000
    checks = run_rule_checks(valid_claim, sample_policy)
    assert _failed(checks) == set()
    assert decide(valid_claim, checks) == "escalate"


def test_low_confidence_escalates(valid_claim, sample_policy):
    valid_claim.extraction_confidence = 0.4
    checks = run_rule_checks(valid_claim, sample_policy)
    assert decide(valid_claim, checks) == "escalate"


def test_bad_date_rejects(valid_claim, sample_policy):
    valid_claim.incident_date = "unknown"
    checks = run_rule_checks(valid_claim, sample_policy)
    assert "within_coverage_period" in _failed(checks)
    assert decide(valid_claim, checks) == "reject"
