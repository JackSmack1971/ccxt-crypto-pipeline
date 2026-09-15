"""Offline acceptance evidence for Phase 7 robust-validation slices."""

import json
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from analysis.experiments import (SplitPolicy, UncertaintyPolicy, bootstrap_mean,
                                  build_walk_forward_evaluation, experiment_spec_dict,
                                  experiment_spec_from_dict, run_experiment)
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
