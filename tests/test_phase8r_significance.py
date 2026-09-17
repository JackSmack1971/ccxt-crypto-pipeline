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
from analysis.datasets import Bar, DatasetSnapshot
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


def test_significance_evidence_rejects_tampered_content_id():
    family = freeze_hypothesis_family(build_spec())
    entry = _evidence_for(family, family.hypotheses[0])
    with pytest.raises(ValueError, match="content does not match its evidence_id"):
        replace(entry, evidence_id="tampered")


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
    observed_through = ("2025-01-13T00:00:00+00:00"
                         if stage == "discovery" else "2025-06-01T00:00:00+00:00")
    entries = [_evidence_for(family, hypothesis, raw_p_value=p_value, stage=stage,
                             dataset_version=snapshot.dataset_identity,
                             observed_through=observed_through)
               for hypothesis, p_value in zip(family.hypotheses, raw_p_values)]
    return build_significance_evidence_bundle(
        family, entries, stage=stage, dataset_version=snapshot.dataset_identity)


def _sequential_snapshot(*, validation_positive=True, holdout_positive=True):
    source = runner_snapshot()
    bars = []
    for bar in source.bars:
        token_index = int(bar.canonical_id.rsplit("tok", 1)[1], 16)
        slope = 0.1 + 0.05 * token_index
        if token_index >= 4 and not validation_positive:
            slope = 0.01
        if token_index >= 6 and not holdout_positive:
            slope = 0.01
        hour = int((bar.timestamp - source.assets[token_index].first_seen).total_seconds() // 3600)
        price = 10 + token_index + hour * slope
        bars.append(Bar(bar.canonical_id, bar.timestamp, price, price, price, price,
                        bar.volume, bar.timeframe, bar.source))
    events = []
    for event in source.events:
        item = dict(event)
        token_index = int(item["canonical_id"].rsplit("tok", 1)[1], 16)
        payload = json.loads(item["payload_json"])
        if token_index in {4, 6}:
            payload["reserve_usd"] = 1_000
        elif token_index in {5, 7}:
            payload["reserve_usd"] = 100_000
        item["payload_json"] = json.dumps(payload)
        events.append(item)
    return DatasetSnapshot(source.assets, tuple(bars), source.metadata, tuple(events), source.lineage,
                            source.policy, source.dataset_identity,
                            asset_relationships=source.asset_relationships,
                            quote_assets=source.quote_assets, reference_series=source.reference_series)


def _sequential_spec(**overrides):
    family = replace(runner_spec().hypothesis_family, thresholds=(">=p25",))
    candidate = replace(runner_spec().candidate, selection_rule="launch_liquidity_usd>=p25")
    policy = replace(runner_spec().promotion_policy, minimum_sample_size=1,
                     minimum_independent_launches=1, minimum_coverage=0.5,
                     minimum_effect_size=0.0001)
    uncertainty = replace(runner_spec().uncertainty, block_size=1)
    stability = replace(runner_spec().stability, dimensions=("leave_one_out",))
    negative_controls = replace(runner_spec().negative_controls,
                                methods=("known_null",), permutations=1)
    falsification = replace(runner_spec().falsification, methods=("known_null", "leave_one_out"))
    return runner_spec(hypothesis_family=family, candidate=candidate,
                       promotion_policy=policy, uncertainty=uncertainty, stability=stability,
                       negative_controls=negative_controls, falsification=falsification, **overrides)


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
    assert manifest["manifest_version"] == "phase8r-run-v2"
    assert manifest["inputs"]["manifest_version"] == "phase8r-run-v2"
    assert {"significance_evidence.json", "significance_evaluation.json"} <= set(manifest["artifacts"])


def test_runner_significance_evidence_changes_immutable_run_identity(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    first = run_experiment(spec, snapshot, tmp_path / "runs",
                           _runner_bundle(spec, snapshot, raw_p_values=(0.01, 0.8)))
    changed = run_experiment(spec, snapshot, tmp_path / "runs",
                             _runner_bundle(spec, snapshot, raw_p_values=(0.2, 0.8)))
    assert first != changed


def test_runner_rejects_confirmation_evidence_in_primary_argument(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    bundle = _runner_bundle(spec, snapshot, stage="confirmation")
    with pytest.raises(ValueError, match="primary significance evidence must be discovery-stage"):
        run_experiment(spec, snapshot, tmp_path / "runs", bundle)


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


def test_runner_rejects_discovery_evidence_observed_after_discovery_boundary(tmp_path):
    spec, snapshot = runner_spec(), runner_snapshot()
    family = freeze_hypothesis_family(spec)
    late_entries = [_evidence_for(
        family, hypothesis, dataset_version=snapshot.dataset_identity,
        observed_through="2025-06-01T00:00:00+00:00")
                    for hypothesis in family.hypotheses]
    late_bundle = build_significance_evidence_bundle(
        family, late_entries, stage="discovery", dataset_version=snapshot.dataset_identity)
    with pytest.raises(ValueError, match="after the discovery/validation boundary"):
        run_experiment(spec, snapshot, tmp_path / "runs", late_bundle)


def test_runner_rejects_confirmation_evidence_before_holdout_boundary(tmp_path):
    spec, snapshot = _sequential_spec(), _sequential_snapshot()
    family = freeze_hypothesis_family(spec)
    entries = _full_evidence(
        family, stage="confirmation", dataset_version=snapshot.dataset_identity,
        observed_through="2025-01-13T00:00:00+00:00")
    bundle = build_significance_evidence_bundle(
        family, entries, stage="confirmation", dataset_version=snapshot.dataset_identity)
    with pytest.raises(ValueError, match="before the validation/holdout boundary"):
        run_experiment(spec, snapshot, tmp_path / "runs", _runner_bundle(spec, snapshot),
                       confirmation_significance_evidence=bundle)


def test_runner_advances_sequentially_to_holdout_with_frozen_selection(tmp_path):
    spec, snapshot = _sequential_spec(), _sequential_snapshot()
    run = run_experiment(
        spec, snapshot, tmp_path / "runs", _runner_bundle(spec, snapshot),
        confirmation_significance_evidence=_runner_bundle(
            spec, snapshot, stage="confirmation"))

    promotion = json.loads((run / "promotion.json").read_text())
    stages = json.loads((run / "promotion_stages.json").read_text())
    split = json.loads((run / "split.json").read_text())
    assert promotion["state"] == "holdout_confirmed"
    assert [item["stage"] for item in stages] == ["discovery", "validation", "holdout"]
    assert all(item["selection_threshold"] == stages[0]["selection_threshold"] for item in stages)
    assert all(item["selected_token_ids"] for item in stages)
    assert all(not set(left["selected_token_ids"]).intersection(right["selected_token_ids"])
               for index, left in enumerate(stages) for right in stages[index + 1:])
    assert split["sealed"] is True
    assert json.loads((run / "confirmation_significance_evaluation.json").read_text())["stage"] == "confirmation"
    assert run_experiment(
        spec, snapshot, tmp_path / "runs", _runner_bundle(spec, snapshot),
        confirmation_significance_evidence=_runner_bundle(spec, snapshot, stage="confirmation")) == run


def test_runner_denominator_is_full_family_even_when_sibling_evidence_is_missing(tmp_path):
    """A caller must not be able to evade discovery/confirmation correction by
    declaring a sibling hypothesis's raw p-value explicitly unavailable. The
    correction burden (m) is the full frozen family, so omitting sibling
    evidence must not make an otherwise-rejected candidate reach
    holdout_confirmed."""
    spec, snapshot = _sequential_spec(), _sequential_snapshot()
    complete = run_experiment(
        spec, snapshot, tmp_path / "runs" / "complete",
        _runner_bundle(spec, snapshot, raw_p_values=(0.04, 0.9)),
        confirmation_significance_evidence=_runner_bundle(
            spec, snapshot, raw_p_values=(0.04, 0.9), stage="confirmation"))
    missing = run_experiment(
        spec, snapshot, tmp_path / "runs" / "missing",
        _runner_bundle(spec, snapshot, raw_p_values=(0.04, None)),
        confirmation_significance_evidence=_runner_bundle(
            spec, snapshot, raw_p_values=(0.04, None), stage="confirmation"))
    complete_promotion = json.loads((complete / "promotion.json").read_text())
    missing_promotion = json.loads((missing / "promotion.json").read_text())
    assert complete_promotion["state"] == missing_promotion["state"] == "rejected"
    assert complete_promotion["inputs"]["discovery_adjusted_p_value"] == pytest.approx(
        missing_promotion["inputs"]["discovery_adjusted_p_value"])


def test_runner_confirmation_evidence_identity_is_canonical_and_scoped_to_consumption(tmp_path):
    """Run identity for confirmation evidence must derive from the validated,
    canonicalized bundle actually persisted -- not the caller's raw container
    object's own (unverified) metadata fields -- and must not depend on
    confirmation evidence that was supplied but never consumed because the
    run never reached validation_confirmed."""
    spec, snapshot = _sequential_spec(), _sequential_snapshot()
    canonical = _runner_bundle(spec, snapshot, stage="confirmation")
    # The confirmation slot only ever consumes `.entries`; a caller-supplied
    # container whose own family_id/dataset_version metadata is stale or
    # wrong must not change run identity, since the real correction is
    # always re-derived from a freshly rebuilt, re-verified bundle.
    junk_metadata = replace(canonical, family_id="not-the-family", dataset_version="not-the-dataset")

    canonical_run = run_experiment(
        spec, snapshot, tmp_path / "runs" / "canonical",
        _runner_bundle(spec, snapshot), confirmation_significance_evidence=canonical)
    junk_metadata_run = run_experiment(
        spec, snapshot, tmp_path / "runs" / "junk-metadata",
        _runner_bundle(spec, snapshot), confirmation_significance_evidence=junk_metadata)
    canonical_manifest = json.loads((canonical_run / "manifest.json").read_text())
    junk_metadata_manifest = json.loads((junk_metadata_run / "manifest.json").read_text())
    assert (canonical_manifest["inputs"]["confirmation_significance_evidence_id"]
            == junk_metadata_manifest["inputs"]["confirmation_significance_evidence_id"])
    assert canonical_manifest["run_id"] == junk_metadata_manifest["run_id"]

    with_unused_confirmation = run_experiment(
        spec, snapshot, tmp_path / "runs" / "with-unused",
        _runner_bundle(spec, snapshot, raw_p_values=(0.9, 0.8)),
        confirmation_significance_evidence=canonical)
    without_confirmation = run_experiment(
        spec, snapshot, tmp_path / "runs" / "without",
        _runner_bundle(spec, snapshot, raw_p_values=(0.9, 0.8)))
    with_unused_manifest = json.loads((with_unused_confirmation / "manifest.json").read_text())
    without_manifest = json.loads((without_confirmation / "manifest.json").read_text())
    assert with_unused_manifest["run_id"] == without_manifest["run_id"]
    assert "confirmation_significance_evidence_id" not in with_unused_manifest["inputs"]


def test_runner_stops_before_validation_when_discovery_fails(tmp_path):
    spec, snapshot = _sequential_spec(), _sequential_snapshot()
    run = run_experiment(
        spec, snapshot, tmp_path / "runs",
        _runner_bundle(spec, snapshot, raw_p_values=(0.9, 0.8)),
        confirmation_significance_evidence=_runner_bundle(spec, snapshot, stage="confirmation"))
    stages = json.loads((run / "promotion_stages.json").read_text())
    assert json.loads((run / "promotion.json").read_text())["state"] == "rejected"
    assert [item["stage"] for item in stages] == ["discovery"]
    assert not (run / "validation_candidate.json").exists()


def test_runner_stops_before_holdout_when_validation_fails(tmp_path):
    spec, snapshot = _sequential_spec(), _sequential_snapshot(validation_positive=False)
    run = run_experiment(spec, snapshot, tmp_path / "runs", _runner_bundle(spec, snapshot))
    stages = json.loads((run / "promotion_stages.json").read_text())
    assert [item["stage"] for item in stages] == ["discovery", "validation"]
    assert json.loads((run / "promotion.json").read_text())["state"] == "rejected"
    assert not (run / "holdout_candidate.json").exists()


def test_runner_reports_holdout_correction_failure_after_validation(tmp_path):
    spec, snapshot = _sequential_spec(), _sequential_snapshot()
    run = run_experiment(
        spec, snapshot, tmp_path / "runs", _runner_bundle(spec, snapshot),
        confirmation_significance_evidence=_runner_bundle(
            spec, snapshot, raw_p_values=(0.9, 0.8), stage="confirmation"))
    stages = json.loads((run / "promotion_stages.json").read_text())
    promotion = json.loads((run / "promotion.json").read_text())
    assert [item["stage"] for item in stages] == ["discovery", "validation", "holdout"]
    assert promotion["state"] == "rejected"
    assert "HOLDOUT_CORRECTION_FAILED" in promotion["reasons"]
