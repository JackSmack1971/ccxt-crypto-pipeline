import json
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from analysis.alpha import CohortConfig, LabelDefinition, PromotionPolicy
from analysis.datasets import Asset, Bar, DatasetPolicy, DatasetSnapshot
from analysis.experiments import (BaselinePolicy, CandidateDefinition, CostPolicy,
                                  ExperimentSpec, HypothesisFamily, SPEC_VERSION, SplitPolicy,
                                  experiment_spec_dict, experiment_spec_id, resolve_feature_registry,
                                  run_experiment)


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


# --- Slice 6.2: deterministic experiment runner -----------------------------

def runner_snapshot() -> DatasetSnapshot:
    """Eight ethereum launches spaced three days apart with full 1h coverage.

    Liquidity increases monotonically with launch order so a top-quartile
    selection rule deterministically selects exactly one discovery-partition
    token, and every label horizon has complete bar coverage.
    """
    t0 = datetime(2025, 1, 1)
    liquidities = [20_000, 30_000, 40_000, 50_000, 60_000, 70_000, 80_000, 90_000]
    assets, events, bars = [], [], []
    for i, liquidity in enumerate(liquidities):
        launch = t0 + timedelta(days=3 * i)
        address = f"0xtok{i}"
        canonical_id = f"ethereum:{address}"
        assets.append(Asset(canonical_id, "dex", "ethereum", address, launch, address))
        events.append({"canonical_id": canonical_id, "event_type": "new_pool_detected", "timestamp": launch,
                       "payload_json": json.dumps({"reserve_usd": liquidity, "token_address": address}),
                       "source": "fixture"})
        for hour in range(26):
            price = 10 + i + hour * 0.1
            bars.append(Bar(canonical_id, launch + timedelta(hours=hour), price, price, price, price, 1, "1h", "fixture"))
    policy = DatasetPolicy(timeframe="1h")
    return DatasetSnapshot(tuple(assets), tuple(bars), (), tuple(events), (), policy, "runner-fixture")


def runner_spec(**overrides) -> ExperimentSpec:
    t0 = datetime(2025, 1, 1)
    fields = {
        "spec_version": SPEC_VERSION,
        "name": "runner-fixture-experiment",
        "cohort": CohortConfig(t0, t0 + timedelta(days=25), chains=("ethereum",)),
        "feature_set": ("launch_liquidity_usd", "lookback_return"),
        "feature_policy_version": "phase3-feature-v1",
        "labels": (LabelDefinition("forward_return_24h", "24h"),),
        "split": SplitPolicy(embargo_days=0, feature_lookback_seconds=0, label_horizon_seconds=24 * 60 * 60),
        "hypothesis_family": HypothesisFamily(
            name="runner-fixture-family",
            features=("launch_liquidity_usd", "lookback_return"),
            thresholds=(">=p75",),
            horizons=("24h",),
        ),
        "candidate": CandidateDefinition("high_liquidity", "24h", "launch_liquidity_usd>=p75", min_coverage=0.2),
        "costs": CostPolicy(),
        "baselines": BaselinePolicy(),
        "promotion_policy": PromotionPolicy(minimum_sample_size=1, minimum_independent_launches=1, minimum_coverage=0.2),
        "code_version": "test-code-v1",
        "config_identity": "test-config-v1",
    }
    fields.update(overrides)
    return ExperimentSpec(**fields)


def test_runner_executes_the_declared_sequence_and_honestly_withholds_significance(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")

    candidate = json.loads((run / "candidate.json").read_text())
    assert candidate["sample_size"] == 1
    assert candidate["independent_launches"] == 1
    assert candidate["coverage"] == pytest.approx(0.25)

    promotion = json.loads((run / "promotion.json").read_text())
    # The runner never invents hypothesis-family significance testing (that is
    # Slice 6.4's job), so promotion must stay honestly unresolved rather than
    # a fabricated pass.
    assert promotion["state"] == "insufficient_evidence"
    assert promotion["reasons"] == ["MISSING_DISCOVERY_CORRECTION"]
    assert promotion["inputs"]["discovery_adjusted_p_value"] is None

    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["manifest_version"] == "phase6-run-v1"
    assert manifest["inputs"]["dataset_identity"] == "runner-fixture"
    assert set(manifest["artifacts"]) == {
        "spec.json", "cohort.json", "features.json", "labels.json",
        "split.json", "baselines.json", "candidate.json", "promotion.json",
    }


def test_runner_replay_is_byte_identical(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    first = run_experiment(spec, snapshot, tmp_path / "runs")
    second = run_experiment(spec, snapshot, tmp_path / "runs")
    assert first == second
    for name in ("manifest.json", "candidate.json", "promotion.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_runner_run_identity_changes_with_the_spec(tmp_path):
    baseline = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    changed = run_experiment(runner_spec(code_version="test-code-v2"), runner_snapshot(), tmp_path / "runs")
    assert baseline != changed


def test_runner_rejects_an_unresolved_feature_identity(tmp_path):
    spec = runner_spec(feature_set=("launch_liquidity_usd", "holder_count_growth"),
                       hypothesis_family=HypothesisFamily(
                           name="x", features=("launch_liquidity_usd", "holder_count_growth"),
                           thresholds=(">=p75",), horizons=("24h",)))
    with pytest.raises(ValueError, match="unsupported experiment feature identity: holder_count_growth"):
        resolve_feature_registry(spec)


def test_runner_rejects_an_unsupported_selection_rule(tmp_path):
    spec = runner_spec(candidate=CandidateDefinition("bad", "24h", "launch_liquidity_usd>1000"))
    with pytest.raises(ValueError, match="unsupported candidate selection rule"):
        run_experiment(spec, runner_snapshot(), tmp_path / "runs")


def test_runner_selection_threshold_is_computed_within_the_discovery_partition_only(tmp_path):
    spec = runner_spec()
    snapshot = runner_snapshot()
    run = run_experiment(spec, snapshot, tmp_path / "runs")
    candidate = json.loads((run / "candidate.json").read_text())
    # Discovery holds the first 60% of 8 launches (4 tokens, liquidity
    # 20k/30k/40k/50k); a >=p75 threshold over just that partition selects
    # only the 50k token, never a validation/holdout launch.
    assert candidate["independent_launches"] == 1
