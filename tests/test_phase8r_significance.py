"""Slices 8R.7a-b: significance evidence and governed correction integration.

The standalone tests cover construction and binding; runner integration tests
cover 8R.7b's correction and immutable-artifact boundary.
"""

import json
from dataclasses import replace
from datetime import datetime

import pytest

from analysis.experiments import (BaselinePolicy, CandidateDefinition, CostPolicy,
                                  ExperimentSpec, FalsificationPolicy, HypothesisFamily,
                                  SPEC_VERSION, SplitPolicy, SignificanceEvidenceBundle,
                                  build_significance_evidence, build_significance_evidence_bundle,
                                  freeze_hypothesis_family, run_experiment)
from analysis.alpha import CohortConfig, LabelDefinition, PromotionPolicy
from test_phase6 import runner_snapshot, runner_spec


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
        "falsification": FalsificationPolicy(),
    }
    fields.update(overrides)
    return ExperimentSpec(**fields)


def _evidence_for(family, hypothesis, *, raw_p_value=0.01, stage="discovery",
                  dataset_version="fixture-v1", statistical_test="permutation_mean_difference",
                  test_version="v1", observed_through="2025-06-01T00:00:00+00:00",
                  provenance="offline-fixture", seed=23, parameters=None):
    return build_significance_evidence(
        hypothesis, family_id=family.family_id, experiment_spec_id=family.experiment_spec_id,
        dataset_version=dataset_version, stage=stage, raw_p_value=raw_p_value,
        statistical_test=statistical_test, test_version=test_version, observed_through=observed_through,
        provenance=provenance, seed=seed, parameters=parameters or {"permutations": 200})


def _full_evidence(family, **kwargs):
    return [_evidence_for(family, item, **kwargs) for item in family.hypotheses]


# --- construction ------------------------------------------------------------

def test_significance_evidence_constructs_and_is_content_addressed():
    family = freeze_hypothesis_family(build_spec())
    entry = _evidence_for(family, family.hypotheses[0])
    replay = _evidence_for(family, family.hypotheses[0])
    assert entry == replay
    assert entry.evidence_id == replay.evidence_id
    changed = _evidence_for(family, family.hypotheses[0], raw_p_value=0.5)
    assert changed.evidence_id != entry.evidence_id


@pytest.mark.parametrize("kwargs,message", [
    ({"raw_p_value": float("nan")}, "finite"),
    ({"raw_p_value": 1.5}, "finite"),
    ({"raw_p_value": -0.1}, "finite"),
    ({"stage": "validation"}, "unsupported significance-evidence stage"),
    ({"observed_through": "not-a-timestamp"}, "invalid significance evidence temporal boundary"),
    ({"provenance": "  "}, "provenance/source identity"),
    ({"statistical_test": ""}, "statistical test identity"),
    ({"dataset_version": ""}, "dataset version"),
    ({"seed": -1}, "non-negative integer"),
])
def test_significance_evidence_rejects_invalid_fields(kwargs, message):
    family = freeze_hypothesis_family(build_spec())
    with pytest.raises(ValueError, match=message):
        _evidence_for(family, family.hypotheses[0], **kwargs)


# --- bundle validation: positive path ----------------------------------------

def test_significance_evidence_bundle_binds_complete_evidence_to_the_frozen_family():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family)
    bundle = build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")
    assert isinstance(bundle, SignificanceEvidenceBundle)
    assert bundle.family_id == family.family_id
    assert bundle.experiment_spec_id == family.experiment_spec_id
    raw = bundle.raw_p_values()
    assert set(raw) == {item.key for item in family.hypotheses}
    assert all(value == 0.01 for value in raw.values())


def test_significance_evidence_bundle_replays_deterministically():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family)
    first = build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")
    second = build_significance_evidence_bundle(family, list(reversed(entries)),
                                                stage="discovery", dataset_version="fixture-v1")
    assert first == second


def test_significance_evidence_bundle_allows_explicit_missing_p_value_per_hypothesis():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family, raw_p_value=None, stage="confirmation")
    bundle = build_significance_evidence_bundle(family, entries, stage="confirmation", dataset_version="fixture-v1")
    assert all(value is None for value in bundle.raw_p_values().values())


# --- bundle validation: fail-closed cases ------------------------------------

def test_significance_evidence_bundle_rejects_missing_hypothesis_evidence():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family)[:-1]
    with pytest.raises(ValueError, match="incomplete for frozen family"):
        build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_extra_hypothesis_evidence():
    family = freeze_hypothesis_family(build_spec())
    other_hypothesis = replace(family.hypotheses[0], feature="undeclared_feature")
    entries = _full_evidence(family) + [_evidence_for(family, other_hypothesis)]
    with pytest.raises(ValueError, match="hypothesis outside the frozen family"):
        build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_duplicate_or_conflicting_evidence():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family) + [_evidence_for(family, family.hypotheses[0], raw_p_value=0.9)]
    with pytest.raises(ValueError, match="duplicate or conflicting significance evidence"):
        build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_wrong_stage():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family, stage="confirmation")
    with pytest.raises(ValueError, match="different stage"):
        build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_unsupported_stage():
    family = freeze_hypothesis_family(build_spec())
    with pytest.raises(ValueError, match="unsupported significance-evidence stage"):
        build_significance_evidence_bundle(family, [], stage="holdout", dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_wrong_dataset_version():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family, dataset_version="fixture-v1")
    with pytest.raises(ValueError, match="different dataset version"):
        build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v2")


def test_significance_evidence_bundle_rejects_wrong_family_binding():
    spec_a, spec_b = build_spec(), build_spec(name="a-different-experiment")
    family_a, family_b = freeze_hypothesis_family(spec_a), freeze_hypothesis_family(spec_b)
    entries = _full_evidence(family_b)
    with pytest.raises(ValueError, match="different hypothesis family"):
        build_significance_evidence_bundle(family_a, entries, stage="discovery", dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_wrong_experiment_spec_binding():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family)
    tampered_entry = build_significance_evidence(
        family.hypotheses[0], family_id=family.family_id,
        experiment_spec_id="a-different-experiment-spec-id", dataset_version="fixture-v1",
        stage="discovery", raw_p_value=0.01, statistical_test="permutation_mean_difference",
        test_version="v1", observed_through="2025-06-01T00:00:00+00:00", provenance="offline-fixture")
    entries = [tampered_entry] + entries[1:]
    with pytest.raises(ValueError, match="different experiment spec"):
        build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_mutated_frozen_family_content():
    family = freeze_hypothesis_family(build_spec())
    tampered = replace(family, hypotheses=family.hypotheses[:-1])
    with pytest.raises(ValueError, match="content does not match its frozen identity"):
        build_significance_evidence_bundle(tampered, _full_evidence(family), stage="discovery",
                                           dataset_version="fixture-v1")


def test_significance_evidence_bundle_rejects_mixed_observation_boundaries():
    family = freeze_hypothesis_family(build_spec())
    entries = _full_evidence(family)
    entries[-1] = _evidence_for(family, family.hypotheses[-1], observed_through="2025-06-02T00:00:00+00:00")
    with pytest.raises(ValueError, match="one observed-through boundary"):
        build_significance_evidence_bundle(family, entries, stage="discovery", dataset_version="fixture-v1")


# --- governed runner integration: Slice 8R.7b -------------------------------

def _runner_bundle(spec, snapshot, *, raw_p_values=(0.01, 0.8), stage="discovery"):
    family = freeze_hypothesis_family(spec)
    entries = [_evidence_for(family, hypothesis, raw_p_value=p_value, stage=stage,
                             dataset_version=snapshot.dataset_identity)
               for hypothesis, p_value in zip(family.hypotheses, raw_p_values)]
    return build_significance_evidence_bundle(
        family, entries, stage=stage, dataset_version=snapshot.dataset_identity)


def test_runner_consumes_bound_discovery_evidence_and_persists_correction(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    bundle = _runner_bundle(spec, snapshot)
    run = run_experiment(spec, snapshot, tmp_path / "runs", bundle)

    promotion = json.loads((run / "promotion.json").read_text())
    assert promotion["inputs"]["discovery_adjusted_p_value"] == pytest.approx(0.02)
    assert promotion["state"] == "rejected"
    evaluation = json.loads((run / "significance_evaluation.json").read_text())
    assert evaluation["family_id"] == bundle.family_id
    assert evaluation["hypotheses"][0]["adjusted_value"] == pytest.approx(0.02)
    manifest = json.loads((run / "manifest.json").read_text())
    assert "significance_evidence_id" in manifest["inputs"]
    assert {"significance_evidence.json", "significance_evaluation.json"} <= set(manifest["artifacts"])


def test_runner_significance_evidence_changes_immutable_run_identity(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    first = run_experiment(spec, snapshot, tmp_path / "runs",
                           _runner_bundle(spec, snapshot, raw_p_values=(0.01, 0.8)))
    changed = run_experiment(spec, snapshot, tmp_path / "runs",
                             _runner_bundle(spec, snapshot, raw_p_values=(0.2, 0.8)))
    assert first != changed


def test_runner_confirmation_evidence_is_corrected_but_not_used_as_discovery(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    bundle = _runner_bundle(spec, snapshot, stage="confirmation")
    run = run_experiment(spec, snapshot, tmp_path / "runs", bundle)
    promotion = json.loads((run / "promotion.json").read_text())
    evaluation = json.loads((run / "significance_evaluation.json").read_text())
    assert promotion["inputs"]["discovery_adjusted_p_value"] is None
    assert evaluation["stage"] == "confirmation"


def test_runner_rejects_evidence_bound_to_another_dataset(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    bundle = _runner_bundle(spec, snapshot)
    other_snapshot = type(snapshot)(snapshot.assets, snapshot.bars, snapshot.metadata, snapshot.events,
                                    snapshot.lineage, snapshot.policy, "other-dataset",
                                    asset_relationships=snapshot.asset_relationships,
                                    quote_assets=snapshot.quote_assets,
                                    reference_series=snapshot.reference_series)
    with pytest.raises(ValueError, match="different dataset version"):
        run_experiment(spec, other_snapshot, tmp_path / "runs", bundle)
