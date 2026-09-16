"""Offline acceptance evidence for the complete Phase 6 control plane."""

import hashlib
import json
from datetime import datetime, timedelta

import pytest

from analysis.alpha import CohortConfig, LabelDefinition, PromotionPolicy
from analysis.datasets import Asset, Bar, DatasetPolicy, DatasetSnapshot
from analysis.experiments import (BaselinePolicy, CandidateDefinition, CostPolicy,
                                  ExperimentSpec, HypothesisFamily, SPEC_VERSION, SplitPolicy,
                                  FalsificationPolicy,
                                  compare_runs, inspect_experiment_run, load_experiment_spec,
                                  run_experiment)


def _spec(**overrides):
    start = datetime(2025, 1, 1)
    values = {
        "spec_version": SPEC_VERSION,
        "name": "phase6-closure-fixture",
        "cohort": CohortConfig(start, start + timedelta(days=25), chains=("ethereum",)),
        "feature_set": ("launch_liquidity_usd", "lookback_return"),
        "feature_policy_version": "phase3-feature-v1",
        "labels": (LabelDefinition("forward_return_24h", "24h"),),
        "split": SplitPolicy(embargo_days=0, feature_lookback_seconds=0,
                             label_horizon_seconds=24 * 60 * 60),
        "hypothesis_family": HypothesisFamily(
            name="phase6-closure-family",
            features=("launch_liquidity_usd", "lookback_return"),
            thresholds=(">=p75",),
            horizons=("24h",),
        ),
        "candidate": CandidateDefinition("high_liquidity", "24h",
                                         "launch_liquidity_usd>=p75", min_coverage=0.2),
        "costs": CostPolicy(),
        "baselines": BaselinePolicy(),
        "promotion_policy": PromotionPolicy(minimum_sample_size=1,
                                             minimum_independent_launches=1,
                                             minimum_coverage=0.2),
        "code_version": "phase6-closure-code-v1",
        "config_identity": "phase6-closure-config-v1",
        "falsification": FalsificationPolicy(),
    }
    values.update(overrides)
    return ExperimentSpec(**values)


def _snapshot(identity="phase6-closure-data-v1", holdout_price_multiplier=1.0):
    start = datetime(2025, 1, 1)
    assets, events, bars = [], [], []
    for index in range(8):
        launch = start + timedelta(days=3 * index)
        address = f"0xclosure{index}"
        canonical_id = f"ethereum:{address}"
        assets.append(Asset(canonical_id, "dex", "ethereum", address, launch, address))
        events.append({"canonical_id": canonical_id, "event_type": "new_pool_detected",
                       "timestamp": launch,
                       "payload_json": json.dumps({"reserve_usd": 20_000 + index * 10_000,
                                                   "token_address": address}),
                       "source": "fixture"})
        multiplier = holdout_price_multiplier if index >= 6 else 1.0
        for hour in range(26):
            price = (10 + index + hour * 0.1) * multiplier
            bars.append(Bar(canonical_id, launch + timedelta(hours=hour), price, price,
                            price, price, 1, "1h", "fixture"))
    return DatasetSnapshot(tuple(assets), tuple(bars), (), tuple(events), (),
                           DatasetPolicy(timeframe="1h"), identity)


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase6_replay_and_manifest_reconstruction_are_complete_and_offline(tmp_path, monkeypatch):
    def deny_network(*_args, **_kwargs):
        raise AssertionError("Phase 6 acceptance must remain offline")

    monkeypatch.setattr("socket.socket", deny_network)
    snapshot = _snapshot()
    first = run_experiment(_spec(), snapshot, tmp_path / "runs")

    # Reconstruct through the public spec boundary, then replay through the sole runner.
    reconstructed = load_experiment_spec(first / "spec.json")
    replay = run_experiment(reconstructed, snapshot, tmp_path / "runs")
    assert replay == first
    assert inspect_experiment_run(replay).run_id == first.name

    manifest = _json(first / "manifest.json")
    declared = manifest["artifacts"]
    assert set(path.name for path in first.iterdir()) == {*declared, "manifest.json"}
    assert all(hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
               for name, digest in declared.items())
    assert len(_json(first / "hypothesis_family.json")["hypotheses"]) == 2


def test_phase6_holdout_is_sealed_and_incompatible_comparison_fails_closed(tmp_path):
    baseline = run_experiment(_spec(), _snapshot(), tmp_path / "runs")
    altered = run_experiment(
        _spec(), _snapshot("phase6-closure-data-holdout-altered", 1000.0), tmp_path / "runs")

    baseline_split = _json(baseline / "split.json")
    assert baseline_split["holdout"] == ["ethereum:0xclosure6", "ethereum:0xclosure7"]
    # Only holdout label evidence changed; discovery scoring and promotion cannot observe it.
    assert (baseline / "labels.json").read_bytes() != (altered / "labels.json").read_bytes()
    assert (baseline / "candidate.json").read_bytes() == (altered / "candidate.json").read_bytes()
    assert (baseline / "promotion.json").read_bytes() == (altered / "promotion.json").read_bytes()

    incompatible = run_experiment(
        _spec(costs=CostPolicy(scenarios=(0.0, 0.002))), _snapshot(), tmp_path / "runs")
    with pytest.raises(ValueError, match="incompatible experiment methodology"):
        compare_runs(baseline, incompatible)
