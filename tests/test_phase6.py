from dataclasses import replace
from datetime import datetime

import pytest

from analysis.alpha import CohortConfig, LabelDefinition, PromotionPolicy
from analysis.experiments import (BaselinePolicy, CandidateDefinition, CostPolicy,
                                  ExperimentSpec, HypothesisFamily, SPEC_VERSION, SplitPolicy,
                                  experiment_spec_dict, experiment_spec_id)


def build_spec(**overrides) -> ExperimentSpec:
    fields = {
        "spec_version": SPEC_VERSION,
        "name": "launch-liquidity-momentum",
        "cohort": CohortConfig(datetime(2025, 1, 1), datetime(2025, 6, 1), chains=("ethereum", "solana")),
        "feature_set": ("launch_liquidity_usd", "lookback_return"),
        "feature_policy_version": "phase3-feature-v1",
        "labels": (LabelDefinition("forward_return_24h", "24h"),),
        "split": SplitPolicy(embargo_days=7, label_horizon_seconds=24 * 60 * 60),
        "hypothesis_family": HypothesisFamily(
            name="launch-liquidity-momentum-family",
            features=("launch_liquidity_usd", "lookback_return"),
            thresholds=(">=p75",),
            horizons=("24h",),
        ),
        "candidate": CandidateDefinition("high_liquidity_momentum", "24h", "launch_liquidity_usd>=p75"),
        "costs": CostPolicy(),
        "baselines": BaselinePolicy(),
        "promotion_policy": PromotionPolicy(),
        "code_version": "abc123",
        "config_identity": "config-v1",
    }
    fields.update(overrides)
    return ExperimentSpec(**fields)


def test_valid_spec_builds_and_normalizes_feature_set_order():
    spec = build_spec(feature_set=("lookback_return", "launch_liquidity_usd"))
    assert spec.feature_set == ("launch_liquidity_usd", "lookback_return")


def test_identical_specs_produce_the_same_deterministic_identity():
    first = experiment_spec_id(build_spec())
    second = experiment_spec_id(build_spec())
    assert first == second
    assert len(first) == 24


def test_changing_split_embargo_changes_identity():
    baseline = experiment_spec_id(build_spec())
    changed = experiment_spec_id(build_spec(split=replace(build_spec().split, embargo_days=14)))
    assert baseline != changed


def test_changing_hypothesis_family_threshold_changes_identity():
    baseline = experiment_spec_id(build_spec())
    family = replace(build_spec().hypothesis_family, thresholds=(">=p90",))
    changed = experiment_spec_id(build_spec(hypothesis_family=family))
    assert baseline != changed


def test_changing_cost_scenario_changes_identity():
    baseline = experiment_spec_id(build_spec())
    changed = experiment_spec_id(build_spec(costs=CostPolicy(scenarios=(0.0, 0.002))))
    assert baseline != changed


def test_experiment_spec_dict_exposes_every_versioned_component():
    payload = experiment_spec_dict(build_spec())
    assert payload["spec_version"] == SPEC_VERSION
    for key in ("cohort", "feature_set", "labels", "split", "hypothesis_family",
                "candidate", "costs", "baselines", "promotion_policy", "code_version", "config_identity"):
        assert key in payload


def test_unsupported_spec_version_fails_closed():
    with pytest.raises(ValueError, match="unsupported experiment spec version"):
        build_spec(spec_version="phase6-experiment-v2")


def test_hypothesis_family_rejects_unsupported_discovery_correction():
    with pytest.raises(ValueError, match="unsupported discovery correction"):
        HypothesisFamily(name="x", features=("f",), thresholds=("t",), horizons=("24h",),
                         discovery_correction="bonferroni")


def test_hypothesis_family_rejects_unsupported_confirmation_correction():
    with pytest.raises(ValueError, match="unsupported confirmation correction"):
        HypothesisFamily(name="x", features=("f",), thresholds=("t",), horizons=("24h",),
                         confirmation_correction="bh")


def test_hypothesis_family_horizon_must_be_declared_by_labels():
    family = replace(build_spec().hypothesis_family, horizons=("7d",))
    with pytest.raises(ValueError, match="undeclared label horizons"):
        build_spec(hypothesis_family=family)


def test_candidate_horizon_must_be_declared_by_labels():
    with pytest.raises(ValueError, match="undeclared label horizon"):
        build_spec(candidate=CandidateDefinition("c", "7d", "rule"))


def test_candidate_horizon_must_be_tested_by_the_hypothesis_family():
    labels = (LabelDefinition("forward_return_24h", "24h"), LabelDefinition("forward_return_7d", "7d"))
    with pytest.raises(ValueError, match="must be tested by the hypothesis family"):
        build_spec(labels=labels, candidate=CandidateDefinition("c", "7d", "rule"))


def test_duplicate_label_horizons_fail_closed():
    labels = (LabelDefinition("a", "24h"), LabelDefinition("b", "24h"))
    with pytest.raises(ValueError, match="unique horizons"):
        build_spec(labels=labels)


def test_split_label_horizon_shorter_than_longest_label_fails_closed():
    with pytest.raises(ValueError, match="shorter than the longest declared label horizon"):
        build_spec(split=SplitPolicy(label_horizon_seconds=3600))


def test_promotion_policy_threshold_must_match_hypothesis_family():
    with pytest.raises(ValueError, match="discovery threshold must match"):
        build_spec(promotion_policy=PromotionPolicy(discovery_q=0.1))


def test_baseline_policy_requires_no_trade_family():
    with pytest.raises(ValueError, match="mandatory no_trade family"):
        BaselinePolicy(families=("market_chain",))


def test_baseline_policy_rejects_unsupported_family():
    with pytest.raises(ValueError, match="unsupported baseline family"):
        BaselinePolicy(families=("no_trade", "made_up"))


def test_cost_policy_rejects_duplicate_scenarios():
    with pytest.raises(ValueError, match="must be unique"):
        CostPolicy(scenarios=(0.0, 0.0))


def test_cost_policy_rejects_negative_turnover():
    with pytest.raises(ValueError, match="non-negative"):
        CostPolicy(turnover=-1.0)


def test_candidate_definition_rejects_coverage_out_of_range():
    with pytest.raises(ValueError, match="minimum coverage"):
        CandidateDefinition("c", "24h", "rule", min_coverage=1.5)


def test_split_policy_rejects_negative_embargo():
    with pytest.raises(ValueError, match="non-negative"):
        SplitPolicy(embargo_days=-1)


def test_hypothesis_family_size_reflects_declared_grid():
    family = HypothesisFamily(name="x", features=("a", "b"), thresholds=(">=p75", ">=p90"),
                              horizons=("1h", "24h"), subgroups=(None, "ethereum"))
    assert family.size == 2 * 2 * 2 * 2


def test_feature_set_rejects_duplicate_entries():
    with pytest.raises(ValueError, match="unique"):
        build_spec(feature_set=("launch_liquidity_usd", "launch_liquidity_usd"))


def test_feature_set_rejects_blank_entries():
    with pytest.raises(ValueError, match="non-blank feature"):
        build_spec(feature_set=("launch_liquidity_usd", "  "))
