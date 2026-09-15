"""Offline acceptance evidence for Phase 7 robust-validation slices."""

import json
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from analysis.experiments import SplitPolicy, build_walk_forward_evaluation, run_experiment
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
