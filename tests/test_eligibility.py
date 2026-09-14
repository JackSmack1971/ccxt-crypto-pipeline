import pytest

from analysis.alpha import ChainEligibility, EligibilityPolicy, evaluate_chain_eligibility


def _row(source, scope, *, completeness_ratio=1.0, max_observed_gap_seconds=60.0,
        expected_interval_seconds=60.0, last_status="success"):
    return {"source": source, "scope": scope, "completeness_ratio": completeness_ratio,
            "max_observed_gap_seconds": max_observed_gap_seconds,
            "expected_interval_seconds": expected_interval_seconds, "last_status": last_status}


def test_healthy_chain_with_full_completeness_is_eligible():
    rows = [_row("evm_rpc", "ethereum")]
    result = evaluate_chain_eligibility(rows, {"ethereum": [("evm_rpc", "ethereum")]})
    assert result["ethereum"] == ChainEligibility("ethereum", True, None, (rows[0],))


def test_chain_with_no_configured_scope_is_explicitly_ineligible():
    result = evaluate_chain_eligibility([], {"ethereum": ()})
    assert result["ethereum"].eligible is False
    assert result["ethereum"].reason == "NO_CONFIGURED_SCOPE"


def test_chain_with_no_recorded_observations_is_explicitly_ineligible():
    result = evaluate_chain_eligibility([], {"ethereum": [("evm_rpc", "ethereum")]})
    assert result["ethereum"].eligible is False
    assert result["ethereum"].reason == "NO_PROVIDER_OBSERVATIONS"


def test_completeness_below_threshold_is_ineligible():
    rows = [_row("evm_rpc", "ethereum", completeness_ratio=0.5)]
    result = evaluate_chain_eligibility(rows, {"ethereum": [("evm_rpc", "ethereum")]},
                                        policy=EligibilityPolicy(min_completeness_ratio=0.9))
    assert result["ethereum"].eligible is False
    assert result["ethereum"].reason == "BELOW_COMPLETENESS_THRESHOLD"


def test_observed_gap_exceeding_explicit_limit_is_ineligible():
    rows = [_row("evm_rpc", "ethereum", max_observed_gap_seconds=500.0)]
    result = evaluate_chain_eligibility(rows, {"ethereum": [("evm_rpc", "ethereum")]},
                                        policy=EligibilityPolicy(max_observed_gap_seconds=300.0))
    assert result["ethereum"].eligible is False
    assert result["ethereum"].reason == "OBSERVED_GAP_EXCEEDS_LIMIT"


def test_observed_gap_exceeding_expected_interval_multiple_is_ineligible():
    rows = [_row("evm_rpc", "ethereum", expected_interval_seconds=60.0, max_observed_gap_seconds=1000.0)]
    result = evaluate_chain_eligibility(rows, {"ethereum": [("evm_rpc", "ethereum")]})
    assert result["ethereum"].eligible is False
    assert result["ethereum"].reason == "OBSERVED_GAP_EXCEEDS_EXPECTED_INTERVAL"


def test_last_observation_failure_is_ineligible_even_with_high_historical_completeness():
    rows = [_row("evm_rpc", "ethereum", completeness_ratio=0.99, last_status="failure")]
    result = evaluate_chain_eligibility(rows, {"ethereum": [("evm_rpc", "ethereum")]})
    assert result["ethereum"].eligible is False
    assert result["ethereum"].reason == "LAST_OBSERVATION_FAILED"


def test_chain_backed_by_multiple_scopes_requires_all_to_pass():
    healthy = _row("helius_enhanced", "program-a")
    unhealthy = _row("helius_enhanced", "program-b", completeness_ratio=0.1)
    result = evaluate_chain_eligibility(
        [healthy, unhealthy],
        {"solana": [("helius_enhanced", "program-a"), ("helius_enhanced", "program-b")]},
    )
    assert result["solana"].eligible is False
    assert result["solana"].reason == "BELOW_COMPLETENESS_THRESHOLD"
    assert result["solana"].quality == (healthy, unhealthy)


def test_policy_rejects_invalid_thresholds():
    with pytest.raises(ValueError, match="min_completeness_ratio"):
        EligibilityPolicy(min_completeness_ratio=0)
    with pytest.raises(ValueError, match="max_observed_gap_seconds"):
        EligibilityPolicy(max_observed_gap_seconds=0)
    with pytest.raises(ValueError, match="max_expected_interval_multiple"):
        EligibilityPolicy(max_expected_interval_multiple=0)
