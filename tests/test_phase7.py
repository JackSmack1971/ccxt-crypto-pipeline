"""Offline acceptance evidence for Phase 7 robust-validation slices."""

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from analysis.experiments import (SplitPolicy, UncertaintyPolicy, bootstrap_mean,
                                  build_walk_forward_evaluation, experiment_spec_dict,
                                  experiment_spec_from_dict, run_experiment, StressPolicy)
from analysis.experiments import NegativeControlPolicy, StabilityPolicy
from analysis.experiments.negative_controls import build_negative_control_evidence
from analysis.experiments.closure import build_validation_closure
from analysis.alpha import baseline_families, score_candidate
from analysis.alpha.labels import LabelRow
from analysis.experiments.stress import _build_stress_matrix
from analysis.experiments.stability import build_stability_evidence
from analysis.experiments.catalog import load_run
from test_phase6 import runner_snapshot, runner_spec


def rows(count=15):
    start = datetime(2025, 1, 1)
    return tuple(SimpleNamespace(token_id=f"token-{index:02d}",
                                 t0=start + timedelta(days=index))
                 for index in range(count))


def test_walk_forward_folds_expand_without_validation_or_holdout_overlap():
    evaluation = build_walk_forward_evaluation(
        rows(), folds=3, embargo_days=0, feature_lookback=timedelta(0),
        label_horizon=timedelta(0))

    assert [fold.train for fold in evaluation.folds] == [
        ("token-00", "token-01", "token-02"),
        ("token-00", "token-01", "token-02", "token-03", "token-04", "token-05"),
        tuple(f"token-{index:02d}" for index in range(9)),
    ]
    assert [fold.validation for fold in evaluation.folds] == [
        ("token-03", "token-04", "token-05"),
        ("token-06", "token-07", "token-08"),
        ("token-09", "token-10", "token-11"),
    ]
    assert evaluation.sealed_holdout == ("token-12", "token-13", "token-14")
    assert not set(evaluation.sealed_holdout).intersection(
        token for fold in evaluation.folds for token in (*fold.train, *fold.validation))


def test_walk_forward_records_fold_purge_and_embargo_deterministically():
    options = dict(folds=2, embargo_days=2, feature_lookback=timedelta(hours=1),
                   label_horizon=timedelta(days=1))
    first = build_walk_forward_evaluation(rows(12), **options)
    second = build_walk_forward_evaluation(tuple(reversed(rows(12))), **options)

    assert first == second
    assert {item["reason"] for fold in first.folds for item in fold.removed} == {
        "LABEL_WINDOW_OVERLAP", "FEATURE_WINDOW_OVERLAP", "EMBARGO"
    }
    assert {item["reason"] for item in first.holdout_removed} == {
        "FEATURE_WINDOW_OVERLAP", "EMBARGO"
    }


def test_walk_forward_rejects_an_undersized_cohort():
    with pytest.raises(ValueError, match="insufficient cohort rows"):
        build_walk_forward_evaluation(rows(3), folds=3, embargo_days=0,
                                      feature_lookback=timedelta(0), label_horizon=timedelta(0))


def test_walk_forward_configuration_is_validated_and_changes_spec_identity():
    with pytest.raises(ValueError, match="unsupported evaluation mode"):
        SplitPolicy(evaluation_mode="rolling")
    with pytest.raises(ValueError, match="at least two folds"):
        SplitPolicy(walk_forward_folds=1)


def test_runner_persists_walk_forward_evidence_only_when_configured(tmp_path):
    split = replace(runner_spec().split, evaluation_mode="walk_forward", walk_forward_folds=2)
    run = run_experiment(runner_spec(split=split), runner_snapshot(), tmp_path / "runs")
    evidence = json.loads((run / "walk_forward.json").read_text())
    manifest = json.loads((run / "manifest.json").read_text())

    assert evidence["version"] == "phase7-walk-forward-v1"
    assert len(evidence["folds"]) == 2
    assert evidence["sealed_holdout"]
    assert len(evidence["results"]) == 2
    assert all(result["selection_threshold"] is not None for result in evidence["results"])
    assert all(result["candidate"]["sample_size"] >= 0 for result in evidence["results"])
    assert "walk_forward.json" in manifest["artifacts"]


def test_moving_block_bootstrap_is_deterministic_and_preserves_policy_identity():
    policy = UncertaintyPolicy(resamples=200, block_size=2, seed=9)
    first = bootstrap_mean((0.01, 0.02, 0.03, 0.04, 0.05), policy)
    second = bootstrap_mean((0.01, 0.02, 0.03, 0.04, 0.05), policy)
    assert first == second
    assert first["status"] == "available"
    assert first["config"] == policy.as_dict()
    assert first["ci95_low"] <= first["estimate"] <= first["ci95_high"]


def test_uncertainty_rejects_unsupported_dependence_and_keeps_gaps_explicit():
    with pytest.raises(ValueError, match="requires ordered_blocks"):
        UncertaintyPolicy(dependence_structure="independent")
    result = bootstrap_mean((), UncertaintyPolicy(resamples=100))
    assert result["status"] == "unavailable"
    assert result["reason"] == "NO_COMPLETE_OBSERVATIONS"
    for field, value in (("resamples", 100.5), ("block_size", 2.5), ("seed", "17")):
        with pytest.raises(ValueError, match="uncertainty"):
            UncertaintyPolicy(**{field: value})


def test_runner_persists_hash_bound_uncertainty_evidence(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    evidence = json.loads((run / "uncertainty.json").read_text())
    manifest = json.loads((run / "manifest.json").read_text())
    assert evidence["method"] == "moving_block_bootstrap"
    assert evidence["config"]["version"] == "phase7-uncertainty-v1"
    assert evidence["scope"] == "selected_candidate_observations"
    candidate = json.loads((run / "candidate.json").read_text())
    assert candidate["uncertainty"]["method"] == evidence["method"]
    assert candidate["uncertainty"]["ci95_low"] == evidence["ci95_low"]
    assert "uncertainty.json" in manifest["artifacts"]


def test_phase6_spec_without_uncertainty_remains_loadable():
    legacy = experiment_spec_dict(runner_spec())
    legacy.pop("uncertainty")
    restored = experiment_spec_from_dict(legacy)
    assert restored.uncertainty == UncertaintyPolicy()


def test_stress_matrix_keeps_selection_fixed_and_reports_missingness():
    labels = (
        SimpleNamespace(token_id="a", horizon="24h", status="COMPLETE", value=0.10),
        SimpleNamespace(token_id="b", horizon="24h", status="DATA_CENSORED", value=None),
    )
    features = ({"token_id": "a", "launch_liquidity_usd": 10_000.0},
                {"token_id": "b", "launch_liquidity_usd": 20_000.0})
    result = _build_stress_matrix(
        selected_token_ids=frozenset({"a", "b"}), labels=labels,
        feature_rows=features, horizon="24h", turnover=1.0,
        policy=StressPolicy(fee_rates=(0.001,), slippage_bps=(100.0,),
                            minimum_liquidity_usd=(5_000.0, 15_000.0),
                            missingness_modes=("exclude_incomplete", "fail_closed")))

    assert result["selected_token_ids"] == ["a", "b"]
    assert len(result["scenarios"]) == 4
    excluded = [row for row in result["scenarios"] if row["missingness_mode"] == "exclude_incomplete"]
    failed = [row for row in result["scenarios"] if row["missingness_mode"] == "fail_closed"]
    assert excluded[0]["status"] == "available" and excluded[0]["sample_size"] == 1
    assert excluded[1]["status"] == "unavailable" and excluded[1]["reason"] == "NO_COMPLETE_OBSERVATIONS"
    assert all(row["status"] == "unavailable" and row["reason"] == "MISSINGNESS_FAIL_CLOSED" for row in failed)

    invalid = _build_stress_matrix(
        selected_token_ids=frozenset({"nan"}),
        labels=(SimpleNamespace(token_id="nan", horizon="24h", status="COMPLETE", value=float("nan")),),
        feature_rows=({"token_id": "nan", "launch_liquidity_usd": 10_000.0},),
        horizon="24h", turnover=0.0,
        policy=StressPolicy(fee_rates=(0.0,), slippage_bps=(0.0,),
                            minimum_liquidity_usd=(0.0,), missingness_modes=("exclude_incomplete",)))
    assert invalid["scenarios"][0]["status"] == "unavailable"
    assert invalid["scenarios"][0]["reason"] == "INVALID_NONFINITE_LABEL"


def test_runner_stress_matrix_does_not_expose_holdout_ids(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    evidence = json.loads((run / "stress_matrix.json").read_text())
    assert evidence["selected_token_ids"] == ["ethereum:0xtok3"]
    assert all("ethereum:0xtok06" not in row["liquidity_excluded_token_ids"]
               for row in evidence["scenarios"])


def test_stability_is_discovery_only_and_reports_concentration(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    evidence = json.loads((run / "stability.json").read_text())
    assert evidence["version"] == "phase7-stability-v1"
    assert evidence["selected_token_ids"] == ["ethereum:0xtok3"]
    assert evidence["dimensions"]["chain"][0]["dominant"] is True
    assert evidence["dimensions"]["leave_one_out"][0]["remaining_sample_size"] == 0
    assert "ethereum:0xtok06" not in evidence["selected_token_ids"]


def test_stability_policy_rejects_ambiguous_configuration():
    with pytest.raises(ValueError, match="unsupported stability dimension"):
        StabilityPolicy(dimensions=("chain", "unknown"))
    with pytest.raises(ValueError, match="dominance threshold"):
        StabilityPolicy(dominance_threshold=0)
    with pytest.raises(ValueError, match="invalid stability policy"):
        StabilityPolicy(version="phase7-stability-v999")


def test_legacy_spec_without_stability_remains_loadable():
    legacy = experiment_spec_dict(runner_spec())
    legacy.pop("stability")
    assert experiment_spec_from_dict(legacy).stability == StabilityPolicy()


def test_stability_uses_decision_time_provider_evidence_and_fails_closed_on_ambiguity():
    t0 = datetime(2025, 1, 1)
    member = SimpleNamespace(token_id="a", chain="ethereum", t0=t0, source_evidence=(
        {"source": "provider-z", "timestamp": t0.isoformat()},
        {"source": "provider-a", "timestamp": (t0 + timedelta(days=1)).isoformat()},))
    label = SimpleNamespace(token_id="a", horizon="24h", status="COMPLETE", value=0.1)
    result = build_stability_evidence(selected_token_ids=frozenset({"a"}), labels=(label,), cohort=(member,),
                                      feature_rows=({"token_id": "a", "launch_liquidity_usd": 20_000.0},),
                                      horizon="24h", policy=StabilityPolicy(dimensions=("provider",)))
    assert result["dimensions"]["provider"][0]["group"] == "provider-z"

    offset_future = SimpleNamespace(token_id="a", chain="ethereum", t0=t0, source_evidence=(
        {"source": "provider-z", "timestamp": "2024-12-31T23:30:00-02:00"},))
    result = build_stability_evidence(selected_token_ids=frozenset({"a"}), labels=(label,), cohort=(offset_future,),
                                      feature_rows=(), horizon="24h", policy=StabilityPolicy(dimensions=("provider",)))
    assert result["dimensions"]["provider"][0]["group"] == "unavailable"

    ambiguous = SimpleNamespace(token_id="a", chain="ethereum", t0=t0, source_evidence=(
        {"source": "provider-a", "timestamp": t0.isoformat()},
        {"source": "provider-b", "timestamp": t0.isoformat()},))
    result = build_stability_evidence(selected_token_ids=frozenset({"a"}), labels=(label,), cohort=(ambiguous,),
                                      feature_rows=(), horizon="24h", policy=StabilityPolicy(dimensions=("provider",)))
    assert result["dimensions"]["provider"][0]["group"] == "ambiguous"


def test_stability_does_not_call_censored_evidence_available_or_dominant():
    result = build_stability_evidence(
        selected_token_ids=frozenset({"a"}),
        labels=(SimpleNamespace(token_id="a", horizon="24h", status="DATA_CENSORED", value=None),),
        cohort=(SimpleNamespace(token_id="a", chain="ethereum", t0=datetime(2025, 1, 1), source_evidence=()),),
        feature_rows=(), horizon="24h", policy=StabilityPolicy(dimensions=("chain",)))
    assert result["status"] == "unavailable"
    assert result["reason"] == "NO_COMPLETE_OBSERVATIONS"
    assert result["dominated"] is False
    assert result["dimensions"]["chain"][0]["dominant"] is False


def test_stability_rejects_missing_subgroup_metadata_as_dominance():
    result = build_stability_evidence(
        selected_token_ids=frozenset({"a"}),
        labels=(SimpleNamespace(token_id="a", horizon="24h", status="COMPLETE", value=0.1),),
        cohort=(SimpleNamespace(token_id="a", chain="", t0=datetime(2025, 1, 1), source_evidence=()),),
        feature_rows=(), horizon="24h", policy=StabilityPolicy(dimensions=("provider",)))
    assert result["dimensions"]["provider"][0]["group"] == "unavailable"
    assert result["dimensions"]["provider"][0]["dominant"] is False


def test_current_run_requires_stability_artifact_at_catalog_boundary(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"].pop("stability.json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="lacks required artifacts"):
        load_run(run)


def test_current_run_requires_validation_closure_at_catalog_boundary(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"].pop("validation_closure.json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="lacks required artifacts"):
        load_run(run)


def test_current_manifest_cannot_be_downgraded_to_legacy_phase7(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["manifest_version"] = "phase7-run-v1"
    manifest["artifacts"].pop("negative_controls.json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="identity-bound"):
        load_run(run)


def test_genuine_legacy_phase7_manifest_remains_loadable(tmp_path):
    current = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    legacy = tmp_path / "legacy" / current.name
    legacy.parent.mkdir()
    shutil.copytree(current, legacy)
    manifest_path = legacy / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["manifest_version"] = "phase7-run-v1"
    manifest["artifacts"].pop("negative_controls.json")
    manifest["inputs"].pop("manifest_version")
    legacy_id = hashlib.sha256(
        (json.dumps(manifest["inputs"], sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()[:24]
    renamed = legacy.parent / legacy_id
    legacy.rename(renamed)
    manifest["run_id"] = legacy_id
    (renamed / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    assert load_run(renamed).run_id == legacy_id


def test_negative_controls_are_deterministic_fixed_selection_and_discovery_only(tmp_path):
    first = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    evidence = json.loads((first / "negative_controls.json").read_text())
    assert evidence["version"] == "phase7-negative-controls-v1"
    assert evidence["selection_scope"] == "discovery_selected_candidate"
    assert len(evidence["results"]) == 26
    assert {row["method"] for row in evidence["results"]} == {"label_permutation", "known_null"}
    assert all(row["synthetic"] is True for row in evidence["results"])
    assert all(row["selected_token_ids"] == ["ethereum:0xtok3"] for row in evidence["results"])
    assert all("ethereum:0xtok06" not in row["selected_token_ids"] for row in evidence["results"])
    assert json.loads((first / "manifest.json").read_text())["artifacts"]["negative_controls.json"]


def test_negative_controls_keep_null_and_missingness_explicit():
    labels = (LabelRow("a", "24h", 0.2, "COMPLETE", "2025-01-01", "2025-01-02", 1.0, 1.2, {}),
              LabelRow("b", "24h", None, "DATA_CENSORED", "2025-01-01", "2025-01-02", None, None, {}))
    result = build_negative_control_evidence(
        selected_token_ids=frozenset({"a"}), labels=labels, horizon="24h", turnover=0.0,
        costs=(0.0,), min_coverage=0.1, policy=NegativeControlPolicy(methods=("known_null",)),
        score_candidate=score_candidate, baseline_families=baseline_families)
    row = result["results"][0]
    assert row["candidate"]["mean_return"] == 0.0
    assert row["candidate"]["baseline_comparison"]["difference"] == 0.0
    assert row["candidate"]["sample_size"] == 1
    with pytest.raises(ValueError, match="unsupported negative-control method"):
        NegativeControlPolicy(methods=("shuffle_features",))
    for kwargs in ({"methods": ("known_null",), "permutations": 0},
                   {"methods": ("known_null",), "permutations": -1},
                   {"methods": ("known_null",), "seed": -1}):
        with pytest.raises(ValueError, match="negative-control"):
            NegativeControlPolicy(**kwargs)


def _closure_inputs():
    return dict(
        spec_id="spec-1", selected_token_ids=frozenset({"a"}),
        promotion={"state": "holdout_confirmed"},
        uncertainty={"version": "u1", "status": "available", "ci95_low": 0.01},
        stress={"version": "s1", "passed": True},
        stability={"version": "st1", "status": "available", "dominated": False},
        negative_controls={"version": "n1", "status": "available", "results": [
            {"candidate": {"baseline_comparison": {"difference": 0.0}}}]},
    )


def test_validation_closure_requires_holdout_confirmation():
    values = _closure_inputs()
    values["promotion"] = {"state": "discovery_promoted"}
    result = build_validation_closure(**values)
    assert result["status"] == "ineligible"
    assert result["reason"] == "PROMOTION_NOT_HOLDOUT_CONFIRMED"
    assert result["components"] == []


@pytest.mark.parametrize(("field", "expected"), [
    ("stress", "ROBUSTNESS_COMPONENT_FAILED"),
    ("stability", "ROBUSTNESS_COMPONENT_FAILED"),
    ("negative_controls", "ROBUSTNESS_COMPONENT_FAILED"),
    ("uncertainty", "ROBUSTNESS_COMPONENT_UNAVAILABLE"),
])
def test_validation_closure_fails_or_marks_unavailable_components(field, expected):
    values = _closure_inputs()
    if field == "stress":
        values[field] = {"version": "s1", "passed": False}
    elif field == "stability":
        values[field] = {"version": "st1", "status": "available", "dominated": True}
    elif field == "negative_controls":
        values[field] = {"version": "n1", "status": "available", "results": [
            {"candidate": {"baseline_comparison": {"difference": 0.1}}}]}
    else:
        values[field] = {"version": "u1", "status": "unavailable"}
    result = build_validation_closure(**values)
    assert result["status"] == ("failed" if expected.endswith("FAILED") else "unavailable")
    assert result["reason"] == expected


def test_validation_closure_is_deterministic_and_passes_only_complete_suite():
    first = build_validation_closure(**_closure_inputs())
    second = build_validation_closure(**_closure_inputs())
    assert first == second
    assert first["status"] == "passed"
    assert {item["name"] for item in first["components"]} == {
        "uncertainty", "stress_matrix", "stability", "negative_controls"
    }


def test_validation_closure_includes_configured_walk_forward_evidence():
    values = _closure_inputs()
    values["walk_forward"] = {"version": "wf1", "folds": [1], "results": [1]}
    result = build_validation_closure(**values)
    assert result["status"] == "passed"
    assert result["components"][0]["name"] == "walk_forward"
