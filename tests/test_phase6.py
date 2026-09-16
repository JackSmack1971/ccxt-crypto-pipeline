import json
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import datetime, timedelta

import pytest

from analysis.alpha import (CandidateResult, CohortConfig, FeatureDefinition, Hypothesis,
                            LabelDefinition, PromotionDecision, PromotionEvidence, PromotionPolicy,
                            assert_feature_versions_compatible, assert_label_versions_compatible,
                            compute_features, extract_cohort, feature_definition_id,
                            feature_policy_versions, generate_labels, label_definition_id,
                            resolve_feature_definition, apply_bh_fdr, apply_holm,
                            evaluate_candidate_promotion)
from analysis.datasets import Asset, Bar, DatasetPolicy, DatasetSnapshot
from analysis.experiments import (BaselinePolicy, CandidateDefinition, CostPolicy,
                                  ExperimentSpec, HypothesisFamily, SPEC_VERSION, SplitPolicy,
                                  evaluate_hypothesis_family, freeze_hypothesis_family,
                                  experiment_spec_dict, experiment_spec_id, resolve_feature_registry,
                                  run_experiment, catalog_runs, compare_runs, load_run,
                                  approve_experiment_run, execute_experiment, inspect_experiment_run,
                                  load_experiment_spec, validate_experiment_spec)
from analysis.experiments.runner import (_dump, _parse_selection_rule, _percentile,
                                         _safe, _selected_token_ids)


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


def promotion_candidate(**overrides) -> CandidateResult:
    values = {
        "name": "candidate",
        "horizon": "24h",
        "sample_size": 10,
        "independent_launches": 10,
        "coverage": 0.8,
        "missingness": 0.0,
        "mean_return": 0.02,
        "uncertainty": {"ci95_low": 0.01},
        "baseline_comparison": {"difference": 0.02},
        "cost_sensitivity": {"base": 0.01},
        "promotion": None,
    }
    values.update(overrides)
    return CandidateResult(**values)


def promotion_evidence(**overrides) -> PromotionEvidence:
    values = {
        "target_stage": "discovery",
        "discovery_adjusted_p_value": 0.05,
        "effect_size": 0.02,
        "baseline_superior": True,
        "uncertainty_supports_effect": True,
        "cost_sensitivity_passed": True,
    }
    values.update(overrides)
    return PromotionEvidence(**values)


def expected_decision(state, reasons, evidence, policy=PromotionPolicy()):
    return PromotionDecision(state, tuple(reasons), asdict(policy), asdict(evidence))


@pytest.mark.parametrize(
    ("field", "below", "at", "above", "reason"),
    [
        ("sample_size", 9, 10, 11, "MINIMUM_SAMPLE_SIZE"),
        ("independent_launches", 9, 10, 11, "MINIMUM_INDEPENDENT_LAUNCHES"),
    ],
)
def test_promotion_count_thresholds_have_exact_three_point_decisions(field, below, at, above, reason):
    evidence = promotion_evidence()
    policy = PromotionPolicy()
    for value in (at, above):
        candidate = promotion_candidate(**{field: value})
        assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
            "discovery_promoted", (), evidence, policy)
    candidate = promotion_candidate(**{field: below})
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "insufficient_coverage", (reason,), evidence, policy)


@pytest.mark.parametrize("coverage", (0.8, 0.8 + 1e-12))
def test_promotion_coverage_at_and_above_threshold_is_discovery_promoted(coverage):
    evidence = promotion_evidence()
    policy = PromotionPolicy()
    candidate = promotion_candidate(coverage=coverage)
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "discovery_promoted", (), evidence, policy)


def test_promotion_coverage_just_below_threshold_changes_reason():
    evidence = promotion_evidence()
    policy = PromotionPolicy()
    candidate = promotion_candidate(coverage=policy.minimum_coverage - 1e-12)
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "insufficient_coverage", ("MINIMUM_COVERAGE",), evidence, policy)


@pytest.mark.parametrize("effect_size", (0.01, 0.01 + 1e-12))
def test_promotion_effect_threshold_at_and_above_is_approved(effect_size):
    policy = PromotionPolicy(minimum_effect_size=0.01)
    candidate = promotion_candidate(
        uncertainty={"ci95_low": effect_size},
        baseline_comparison={"difference": effect_size},
    )
    evidence = promotion_evidence(effect_size=effect_size)
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "discovery_promoted", (), evidence, policy)


def test_promotion_effect_just_below_threshold_changes_reason():
    policy = PromotionPolicy(minimum_effect_size=0.01)
    effect_size = policy.minimum_effect_size - 1e-12
    candidate = promotion_candidate(
        uncertainty={"ci95_low": effect_size},
        baseline_comparison={"difference": effect_size},
    )
    evidence = promotion_evidence(effect_size=effect_size)
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "rejected", ("PRACTICAL_EFFECT_TOO_SMALL",), evidence, policy)


@pytest.mark.parametrize("p_value", (0.05, 0.05 - 1e-12))
def test_promotion_discovery_q_boundary_approves_at_or_below(p_value):
    policy = PromotionPolicy(discovery_q=0.05)
    evidence = promotion_evidence(discovery_adjusted_p_value=p_value)
    candidate = promotion_candidate()
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "discovery_promoted", (), evidence, policy)


def test_promotion_discovery_q_just_above_changes_reason():
    policy = PromotionPolicy(discovery_q=0.05)
    evidence = promotion_evidence(discovery_adjusted_p_value=policy.discovery_q + 1e-12)
    candidate = promotion_candidate()
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "rejected", ("DISCOVERY_CORRECTION_FAILED",), evidence, policy)


@pytest.mark.parametrize("p_value", (0.05, 0.05 - 1e-12))
def test_promotion_holdout_alpha_boundary_confirms_at_or_below(p_value):
    policy = PromotionPolicy(confirmation_alpha=0.05)
    evidence = promotion_evidence(
        target_stage="holdout", validation_replicated=True,
        validation_semantics_frozen=True, holdout_adjusted_p_value=p_value)
    candidate = promotion_candidate()
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "holdout_confirmed", (), evidence, policy)


def test_promotion_holdout_alpha_just_above_changes_reason():
    policy = PromotionPolicy(confirmation_alpha=0.05)
    evidence = promotion_evidence(
        target_stage="holdout", validation_replicated=True,
        validation_semantics_frozen=True,
        holdout_adjusted_p_value=policy.confirmation_alpha + 1e-12)
    candidate = promotion_candidate()
    assert evaluate_candidate_promotion(candidate, evidence, policy) == expected_decision(
        "rejected", ("HOLDOUT_CORRECTION_FAILED",), evidence, policy)


def _hypothesis(p_value):
    return Hypothesis("experiment", "feature", (), "threshold", "24h", None,
                      "model", "2025-01-01", "dataset", p_value)


def test_bh_fdr_promotes_a_p_value_exactly_at_corrected_q_threshold():
    original = _hypothesis(0.05)
    assert apply_bh_fdr([original], q=0.05) == (
        replace(original, adjusted_value=0.05, decision="promoted"),)


def test_holm_promotes_a_p_value_exactly_at_corrected_alpha_threshold():
    original = _hypothesis(0.05)
    assert apply_holm([original], alpha=0.05) == (
        replace(original, adjusted_value=0.05, decision="confirmed"),)


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


# --- Slice 6.2: deterministic runner helper contracts ----------------------

@pytest.mark.parametrize("rule, expected", [
    ("launch_liquidity_usd>=p0", ("launch_liquidity_usd", ">=", 0.0)),
    (" lookback_return<p100 ", ("lookback_return", "<", 100.0)),
    ("launch_liquidity_usd==p50", ("launch_liquidity_usd", "==", 50.0)),
])
def test_selection_rule_parser_accepts_supported_operators_and_boundaries(rule, expected):
    assert _parse_selection_rule(rule) == expected


@pytest.mark.parametrize("rule, message", [
    ("launch_liquidity_usd>=p101", "percentile out of range"),
    ("launch_liquidity_usd>=p-1", "unsupported candidate selection rule"),
    ("launch_liquidity_usd>=p", "unsupported candidate selection rule"),
    ("launch_liquidity_usd!=p50", "unsupported candidate selection rule"),
    ("launch-liquidity_usd>=p50", "unsupported candidate selection rule"),
])
def test_selection_rule_parser_rejects_malformed_or_out_of_range_rules(rule, message):
    with pytest.raises(ValueError, match=message):
        _parse_selection_rule(rule)


def test_percentile_interpolates_and_preserves_single_value():
    assert _percentile([30.0, 10.0, 20.0], 50.0) == pytest.approx(20.0)
    assert _percentile([10.0, 20.0], 25.0) == pytest.approx(12.5)
    assert _percentile([42.0], 75.0) == 42.0


@pytest.mark.parametrize("rule, expected", [
    ("launch_liquidity_usd>=p50", frozenset({"a", "c"})),
    ("launch_liquidity_usd<p50", frozenset({"b"})),
    ("lookback_return==p50", frozenset({"a", "c"})),
])
def test_selected_token_ids_filters_missing_and_non_finite_values(rule, expected):
    rows = (
        {"token_id": "a", "launch_liquidity_usd": 10.0, "lookback_return": 0.1},
        {"token_id": "b", "launch_liquidity_usd": 5.0, "lookback_return": None},
        {"token_id": "c", "launch_liquidity_usd": 15.0, "lookback_return": 0.1},
        {"token_id": "ignored", "launch_liquidity_usd": float("nan"), "lookback_return": 0.2},
    )
    assert _selected_token_ids(rows, rule) == expected


def test_selected_token_ids_rejects_unsupported_feature_and_empty_values():
    with pytest.raises(ValueError, match="unsupported candidate selection feature"):
        _selected_token_ids(({"token_id": "a", "other": 1.0},), "other>=p50")
    assert _selected_token_ids(({"token_id": "a", "launch_liquidity_usd": None},),
                              "launch_liquidity_usd>=p50") == frozenset()


def test_manifest_serialization_redacts_secret_fields_and_url_credentials():
    value = {"api_key": "hidden", "nested": {"password": "also-hidden"},
             "endpoint": "https://user:pass@example.test/rpc", "public": "kept"}
    sanitized = _safe(value)
    assert sanitized == {"api_key": "[REDACTED]", "nested": {"password": "[REDACTED]"},
                         "endpoint": "https://[REDACTED]@example.test/rpc", "public": "kept"}
    assert b"hidden" not in _dump(value)
    assert b"user:pass" not in _dump(value)


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


def write_spec(path, spec=None):
    path.write_text(json.dumps(experiment_spec_dict(spec or runner_spec()), default=str))
    return path


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
    assert manifest["manifest_version"] == "phase7-run-v3"
    assert manifest["inputs"]["dataset_identity"] == "runner-fixture"
    assert set(manifest["artifacts"]) == {
        "spec.json", "cohort.json", "features.json", "labels.json",
        "split.json", "baselines.json", "candidate.json", "promotion.json",
        "definitions.json",
        "hypothesis_family.json",
        "uncertainty.json",
        "stress_matrix.json",
        "stability.json",
        "negative_controls.json",
        "validation_closure.json",
    }

    definitions = json.loads((run / "definitions.json").read_text())
    assert definitions["features"]["launch_liquidity_usd"]["version"] == "v1"
    assert definitions["features"]["lookback_return"]["version"] == "v1"
    assert definitions["labels"]["24h"]["version"] == "v1"
    assert all(len(entry["definition_id"]) == 24
              for family in definitions.values() for entry in family.values())


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
    # ExperimentSpec now fails closed on an unresolved feature identity at
    # construction time via the durable registry catalog, before a runner
    # ever gets to resolve it.
    with pytest.raises(ValueError, match="unsupported experiment feature identity: holder_count_growth"):
        runner_spec(feature_set=("launch_liquidity_usd", "holder_count_growth"),
                   hypothesis_family=HypothesisFamily(
                       name="x", features=("launch_liquidity_usd", "holder_count_growth"),
                       thresholds=(">=p75",), horizons=("24h",)))


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


# --- Slice 6.5: verified run catalog and comparisons -----------------------

def test_catalog_indexes_verified_runs_deterministically_without_writing(tmp_path):
    root = tmp_path / "runs"
    second = run_experiment(runner_spec(code_version="test-code-v2"), runner_snapshot(), root)
    first = run_experiment(runner_spec(), runner_snapshot(), root)
    before = {path: path.read_bytes() for path in root.glob("*/*")}

    records = catalog_runs(root)

    assert [record.run_id for record in records] == sorted((first.name, second.name))
    assert records[0].dataset_identity == "runner-fixture"
    assert records[0].promotion_state == "insufficient_evidence"
    assert {path: path.read_bytes() for path in root.glob("*/*")} == before


def test_catalog_rejects_tampered_artifact_and_run_identity(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    (run / "candidate.json").write_text("{}\n")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        load_run(run)

    intact = run_experiment(runner_spec(code_version="other"), runner_snapshot(), tmp_path / "runs")
    renamed = intact.with_name("not-the-run-id")
    intact.rename(renamed)
    with pytest.raises(ValueError, match="manifest structure"):
        load_run(renamed)


def test_compatible_runs_can_be_compared(tmp_path):
    left = run_experiment(runner_spec(name="left"), runner_snapshot(), tmp_path / "runs")
    right = run_experiment(runner_spec(name="right"), runner_snapshot(), tmp_path / "runs")

    comparison = compare_runs(left, right)

    assert comparison.candidate_name == "high_liquidity"
    assert comparison.horizon == "24h"
    assert comparison.mean_return_delta == pytest.approx(0.0)
    assert comparison.sample_size_delta == 0


def test_comparison_rejects_incompatible_methodology(tmp_path):
    left = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    changed = runner_spec(costs=CostPolicy(scenarios=(0.0, 0.002)))
    right = run_experiment(changed, runner_snapshot(), tmp_path / "runs")

    with pytest.raises(ValueError, match="incompatible experiment methodology"):
        compare_runs(left, right)


# --- Slice 6.3: feature/label registry versioning ---------------------------

def test_feature_definition_requires_a_version():
    with pytest.raises(ValueError, match="requires a version"):
        FeatureDefinition("x", ("col",), "t0", timedelta(0), version=" ")


def test_feature_definition_id_is_deterministic_and_changes_with_version():
    base = FeatureDefinition("x", ("col",), "t0", timedelta(0))
    same = FeatureDefinition("x", ("col",), "t0", timedelta(0))
    bumped = FeatureDefinition("x", ("col",), "t0", timedelta(0), version="v2")
    assert feature_definition_id(base) == feature_definition_id(same)
    assert feature_definition_id(base) != feature_definition_id(bumped)


def test_feature_definition_id_ignores_the_compute_callable():
    # The catalog, not the raw dataclass, governs compute behavior per
    # version; two definitions with identical declared metadata but
    # different compute functions still share an identity, so a version bump
    # is the only supported way to signal a behavior change.
    declared = dict(name="x", source_columns=("col",), effective_timestamp="t0", lookback=timedelta(0))
    a = FeatureDefinition(**declared, compute=lambda member, bars: 1)
    b = FeatureDefinition(**declared, compute=lambda member, bars: 2)
    assert feature_definition_id(a) == feature_definition_id(b)


def test_label_definition_rejects_unimplemented_version():
    with pytest.raises(ValueError, match="unsupported label semantic version"):
        LabelDefinition("return_24h", "24h", version="v2")


def test_label_definition_id_is_deterministic_and_changes_with_censoring_policy():
    base = LabelDefinition("return_24h", "24h")
    same = LabelDefinition("return_24h", "24h")
    changed = replace(base, censoring_policy="custom_policy")
    assert label_definition_id(base) == label_definition_id(same)
    assert label_definition_id(base) != label_definition_id(changed)


def test_feature_policy_versions_resolves_a_known_policy():
    versions = feature_policy_versions("phase3-feature-v1")
    assert versions == {"launch_liquidity_usd": "v1", "lookback_return": "v1"}


def test_feature_policy_versions_fails_closed_on_an_unknown_policy():
    with pytest.raises(ValueError, match="unsupported feature policy version"):
        feature_policy_versions("made-up-policy")


def test_resolve_feature_definition_fails_closed_on_an_unknown_pair():
    with pytest.raises(ValueError, match="unsupported feature identity: launch_liquidity_usd@v9"):
        resolve_feature_definition("launch_liquidity_usd", "v9")


def test_assert_feature_versions_compatible_allows_identical_versions():
    assert_feature_versions_compatible("launch_liquidity_usd", "v1", "v1")


def test_assert_feature_versions_compatible_fails_closed_on_undeclared_pair():
    with pytest.raises(ValueError, match="incompatible feature versions"):
        assert_feature_versions_compatible("launch_liquidity_usd", "v1", "v2")


def test_assert_label_versions_compatible_allows_identical_versions():
    assert_label_versions_compatible("24h", "v1", "v1")


def test_assert_label_versions_compatible_fails_closed_on_undeclared_pair():
    with pytest.raises(ValueError, match="incompatible label versions"):
        assert_label_versions_compatible("24h", "v1", "v2")


def test_feature_row_provenance_carries_the_resolved_definition_identity():
    spec = runner_spec()
    snapshot = runner_snapshot()
    registry = resolve_feature_registry(spec)
    definition = registry.get("launch_liquidity_usd")
    cohort = extract_cohort(snapshot, spec.cohort)
    feature_rows = compute_features(snapshot, cohort, registry)
    provenance = feature_rows[0]["feature_provenance"]["launch_liquidity_usd"]
    assert provenance["feature_version"] == "v1"
    assert provenance["feature_definition_id"] == feature_definition_id(definition)


def test_label_row_provenance_carries_the_definition_identity():
    spec = runner_spec()
    snapshot = runner_snapshot()
    cohort = extract_cohort(snapshot, spec.cohort)
    label = spec.labels[0]
    rows = generate_labels(snapshot, cohort, label)
    assert rows[0].provenance["label_version"] == "v1"
    assert rows[0].provenance["label_definition_id"] == label_definition_id(label)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("version", "  ", "requires a version"),
        ("embargo_days", -1, "non-negative"),
        ("feature_lookback_seconds", -1, "non-negative"),
        ("label_horizon_seconds", -1, "non-negative"),
    ],
)
def test_split_policy_rejects_invalid_identity_and_windows(field, value, message):
    with pytest.raises(ValueError, match=message):
        SplitPolicy(**{field: value})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", "  ", "requires a name"),
        ("features", (), "at least one non-blank feature"),
        ("thresholds", (), "at least one non-blank threshold"),
        ("horizons", (), "at least one non-blank horizon"),
        ("subgroups", (), "at least one subgroup declaration"),
        ("features", ("a", "a"), "features must be unique"),
        ("thresholds", ("t", "t"), "thresholds must be unique"),
        ("horizons", ("24h", "24h"), "horizons must be unique"),
        ("subgroups", (None, None), "subgroups must be unique"),
        ("discovery_q", 0.0, "thresholds must be in"),
        ("confirmation_alpha", 1.1, "thresholds must be in"),
    ],
)
def test_hypothesis_family_rejects_invalid_grid_and_correction_contract(field, value, message):
    kwargs = {"name": "family", "features": ("a",), "thresholds": ("t",), "horizons": ("24h",)}
    kwargs[field] = value
    with pytest.raises(ValueError, match=message):
        HypothesisFamily(**kwargs)


@pytest.mark.parametrize("kwargs", [{"name": "  "}, {"selection_rule": "  "}])
def test_candidate_definition_rejects_blank_identity_parts(kwargs):
    with pytest.raises(ValueError, match="requires a name and selection rule"):
        CandidateDefinition(**{"name": "candidate", "horizon": "24h", "selection_rule": "rule", **kwargs})


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"version": "  "}, "requires a version"),
        ({"scenarios": ()}, "at least one scenario"),
        ({"scenarios": (-0.001,)}, "non-negative"),
    ],
)
def test_cost_policy_rejects_invalid_identity_and_scenarios(kwargs, message):
    with pytest.raises(ValueError, match=message):
        CostPolicy(**kwargs)


def test_baseline_policy_rejects_duplicate_families():
    with pytest.raises(ValueError, match="must be unique"):
        BaselinePolicy(families=("no_trade", "no_trade"))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"feature_policy_version": "  "}, "feature policy version"),
        ({"code_version": "  "}, "code and config identities"),
        ({"config_identity": "  "}, "code and config identities"),
    ],
)
def test_experiment_spec_rejects_blank_required_identity(kwargs, message):
    with pytest.raises(ValueError, match=message):
        build_spec(**kwargs)


# --- Slice 6.4: hypothesis-family governance -------------------------------

def test_frozen_hypothesis_family_expands_the_exact_grid_deterministically():
    family = freeze_hypothesis_family(build_spec())
    replay = freeze_hypothesis_family(build_spec())
    assert family == replay
    assert family.family_id == replay.family_id
    assert len(family.hypotheses) == build_spec().hypothesis_family.size == 2
    assert len({item.key for item in family.hypotheses}) == 2


def test_family_identity_changes_when_the_predeclared_grid_changes():
    original = freeze_hypothesis_family(build_spec())
    changed_spec = build_spec(hypothesis_family=replace(
        build_spec().hypothesis_family, thresholds=(">=p75", ">=p90")))
    assert freeze_hypothesis_family(changed_spec).family_id != original.family_id


def test_family_evaluation_rejects_post_result_narrowing_or_widening():
    family = freeze_hypothesis_family(build_spec())
    complete = {item.key: 0.01 for item in family.hypotheses}
    narrowed = dict(complete)
    narrowed.pop(next(iter(narrowed)))
    with pytest.raises(ValueError, match="do not match frozen family.*missing=1, extra=0"):
        evaluate_hypothesis_family(family, narrowed, stage="discovery",
                                   dataset_version="fixture", date_tested="2025-01-01")
    with pytest.raises(ValueError, match="do not match frozen family.*missing=0, extra=1"):
        evaluate_hypothesis_family(family, {**complete, "post-hoc": 0.01}, stage="discovery",
                                   dataset_version="fixture", date_tested="2025-01-01")


def test_family_evaluation_binds_correction_results_to_frozen_family():
    family = freeze_hypothesis_family(build_spec())
    raw = {item.key: value for item, value in zip(family.hypotheses, (0.01, 0.8))}
    result = evaluate_hypothesis_family(family, raw, stage="discovery",
                                        dataset_version="fixture", date_tested="2025-01-01")
    assert result.family_id == family.family_id
    assert result.correction == "benjamini-hochberg"
    assert [item.adjusted_value for item in result.hypotheses] == pytest.approx((0.02, 0.8))


def test_family_evaluation_preserves_explicit_unavailable_result():
    family = freeze_hypothesis_family(build_spec())
    raw = {item.key: None for item in family.hypotheses}
    result = evaluate_hypothesis_family(family, raw, stage="confirmation",
                                        dataset_version="fixture", date_tested="2025-01-01")
    assert all(item.adjusted_value is None and item.decision == "rejected"
               for item in result.hypotheses)


def test_family_evaluation_rejects_family_content_changed_after_freeze():
    family = freeze_hypothesis_family(build_spec())
    changed = replace(family, hypotheses=family.hypotheses[:-1])
    with pytest.raises(ValueError, match="content does not match its frozen identity"):
        evaluate_hypothesis_family(changed, {}, stage="discovery",
                                   dataset_version="fixture", date_tested="2025-01-01")


def test_hypothesis_family_features_must_be_declared_by_the_experiment():
    with pytest.raises(ValueError, match="undeclared experiment features"):
        build_spec(hypothesis_family=replace(build_spec().hypothesis_family,
                                             features=("launch_liquidity_usd", "undeclared")))


# --- Slice 6.6: narrow experiment control API/CLI --------------------------

def test_control_api_round_trips_validation_and_uses_existing_runner(tmp_path):
    spec_path = write_spec(tmp_path / "spec.json")
    loaded = load_experiment_spec(spec_path)
    assert experiment_spec_dict(loaded) == experiment_spec_dict(runner_spec())
    assert validate_experiment_spec(spec_path) == experiment_spec_id(runner_spec())
    run = execute_experiment(spec_path, runner_snapshot(), tmp_path / "runs")
    assert inspect_experiment_run(run) == load_run(run)


def test_spec_file_rejects_unknown_fields(tmp_path):
    payload = experiment_spec_dict(runner_spec())
    payload["unreviewed_override"] = True
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(payload, default=str))
    with pytest.raises(ValueError, match="fields do not match schema"):
        load_experiment_spec(path)


def test_approval_is_separate_immutable_attestation_over_verified_run(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    before = {path.name: path.read_bytes() for path in run.iterdir()}
    approval = approve_experiment_run(
        run, tmp_path / "approvals", reviewer="Research Reviewer",
        reviewed_at="2026-09-15T12:00:00Z", rationale="Reviewed the immutable local result.")
    payload = json.loads(approval.read_text())
    assert payload["decision"] == "approved"
    assert payload["run_id"] == run.name
    assert {path.name: path.read_bytes() for path in run.iterdir()} == before
    assert approve_experiment_run(
        run, tmp_path / "approvals", reviewer="Research Reviewer",
        reviewed_at="2026-09-15T12:00:00Z", rationale="Reviewed the immutable local result.") == approval


def test_approval_rejects_unattributed_or_tampered_run(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    with pytest.raises(ValueError, match="reviewer and rationale"):
        approve_experiment_run(run, tmp_path / "approvals", reviewer="", reviewed_at="2026-09-15T12:00:00Z",
                               rationale="reviewed")
    (run / "candidate.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        approve_experiment_run(run, tmp_path / "approvals", reviewer="Reviewer",
                               reviewed_at="2026-09-15T12:00:00Z", rationale="reviewed")


def test_cli_validate_inspect_and_approve_delegate_to_control_boundaries(tmp_path):
    spec_path = write_spec(tmp_path / "spec.json")
    validated = subprocess.run([sys.executable, "-m", "analysis.experiments", "validate", str(spec_path)],
                               check=True, capture_output=True, text=True)
    assert json.loads(validated.stdout)["experiment_spec_id"] == experiment_spec_id(runner_spec())
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    inspected = subprocess.run([sys.executable, "-m", "analysis.experiments", "inspect", str(run)],
                               check=True, capture_output=True, text=True)
    assert json.loads(inspected.stdout)["run_id"] == run.name
    approved = subprocess.run([
        sys.executable, "-m", "analysis.experiments", "approve", str(run),
        "--approval-dir", str(tmp_path / "approvals"), "--reviewer", "Reviewer",
        "--reviewed-at", "2026-09-15T12:00:00Z", "--rationale", "Reviewed immutable output",
    ], check=True, capture_output=True, text=True)
    assert (tmp_path / "approvals" / run.name / (json.loads(approved.stdout)["approval_id"] + ".json")).is_file()
