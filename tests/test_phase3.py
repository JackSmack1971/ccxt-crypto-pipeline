import json
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from analysis.alpha import (CohortConfig, FeatureDefinition, FeatureRegistry, HORIZONS,
                            Hypothesis, LabelDefinition, apply_bh_fdr, apply_holm,
                            build_split, compute_features, extract_cohort, generate_labels, normalize_usd_price,
                            descriptive_baseline, phase2_strategy_spec, rank_candidates, score_candidate, write_research_run,
                            validate_temporal_alignment, baseline_comparison, HypothesisRegistry,
                            PromotionEvidence, evaluate_candidate_promotion,
                            PromotionPolicy,
                            ConversionObservation, ConversionPolicy,
                            EligibilityPolicy, evaluate_chain_eligibility)
from analysis.alpha.features import close_return_feature, launch_liquidity_feature
from analysis.datasets import Asset, Bar, DatasetPolicy, DatasetSnapshot
from ingestion.dex.tier0.poller import poll_network
from storage.db import connect, insert_event, insert_ohlcv_batch, upsert_asset


def snapshot():
    t = datetime(2025, 1, 1)
    assets = (Asset("ethereum:0xaaa", "dex", "ethereum", "0xaaa", t, "0xaaa"),
              Asset("solana:mint", "dex", "solana", "mint", t, "mint"))
    bars = []
    for asset in assets:
        for i in range(8):
            price = 10 + i
            bars.append(Bar(asset.canonical_id, t + timedelta(hours=i), price, price, price, price, 1, "1h", "fixture"))
    events = (
        {"canonical_id": "ethereum:0xaaa", "event_type": "new_pool_detected", "timestamp": t,
         "payload_json": '{"reserve_usd": 12000, "token_address": "0xaaa"}', "source": "rpc"},
        {"canonical_id": "ethereum:0xaaa", "event_type": "new_pool_detected", "timestamp": t,
         "payload_json": '{"reserve_usd": 12000, "token_address": "0xaaa"}', "source": "aggregator"},
        {"canonical_id": "solana:mint", "event_type": "token_mint_detected", "timestamp": t + timedelta(hours=1),
         "payload_json": '{"mint": "mint", "reserve_usd": 4000}', "source": "helius"},
    )
    return DatasetSnapshot(assets, tuple(bars), (), events, (), DatasetPolicy(timeframe="1h", end=t + timedelta(hours=7)), "fixture")


def test_cohort_deduplicates_launches_and_preserves_liquidity_exclusion():
    result = extract_cohort(snapshot(), CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum", "solana")))
    assert [row.token_id for row in result] == ["ethereum:0xaaa", "solana:mint"]
    assert result[0].analysis_eligible is True
    assert result[1].exclusion_reason == "BELOW_LIQUIDITY_GATE"
    assert len(result[0].source_evidence) == 2


def test_cohort_excludes_a_chain_whose_provider_quality_fails_the_gate():
    quality_rows = [{"source": "evm_rpc", "scope": "ethereum", "completeness_ratio": 0.4,
                     "max_observed_gap_seconds": 60.0, "expected_interval_seconds": 60.0,
                     "last_status": "success"}]
    chain_eligibility = evaluate_chain_eligibility(quality_rows, {"ethereum": [("evm_rpc", "ethereum")]})
    config = CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum", "solana"),
                          chain_eligibility=chain_eligibility)
    result = extract_cohort(snapshot(), config)
    ethereum_row = next(row for row in result if row.chain == "ethereum")
    assert ethereum_row.included is True
    assert ethereum_row.analysis_eligible is False
    assert ethereum_row.exclusion_reason == "CHAIN_PROVIDER_QUALITY_INELIGIBLE"
    assert ethereum_row.provenance["chain_eligibility"] == {
        "eligible": False, "reason": "BELOW_COMPLETENESS_THRESHOLD",
    }
    # An unaffected chain's eligibility is decided independently.
    solana_row = next(row for row in result if row.chain == "solana")
    assert solana_row.exclusion_reason == "BELOW_LIQUIDITY_GATE"


def test_cohort_keeps_prior_behavior_when_a_chain_has_no_eligibility_evidence():
    chain_eligibility = evaluate_chain_eligibility([], {"ethereum": [("evm_rpc", "ethereum")]})
    assert chain_eligibility["ethereum"].reason == "NO_PROVIDER_OBSERVATIONS"
    config = CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",),
                          chain_eligibility=chain_eligibility)
    result = extract_cohort(snapshot(), config)
    assert result[0].exclusion_reason == "CHAIN_PROVIDER_QUALITY_INELIGIBLE"


def test_cohort_is_unaffected_by_default_when_no_chain_eligibility_is_supplied():
    result = extract_cohort(snapshot(), CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    assert result[0].analysis_eligible is True
    assert result[0].provenance["chain_eligibility"] is None


def test_pool_constituents_are_address_scoped_and_relationships_are_point_in_time():
    t0 = datetime(2025, 1, 1)
    assets = (
        Asset("ethereum:0xpool", "dex", "ethereum", "SAME", t0, "0xpool"),
        Asset("ethereum:0xbase", "dex", "ethereum", "SAME", t0, "0xbase"),
        Asset("ethereum:0xquote", "dex", "ethereum", "SAME", t0, "0xquote"),
    )
    event = ({"canonical_id": "ethereum:0xpool", "event_type": "new_pool_detected", "timestamp": t0,
              "payload_json": '{"reserve_usd": 12000}', "source": "fixture"},)
    relationships = (
        {"market_canonical_id": "ethereum:0xpool", "asset_canonical_id": "ethereum:0xbase",
         "relationship_type": "base", "venue": "dex", "observed_at": t0,
         "source": "fixture", "evidence_json": "{}"},
        {"market_canonical_id": "ethereum:0xpool", "asset_canonical_id": "ethereum:0xquote",
         "relationship_type": "quote", "venue": "dex", "observed_at": t0 + timedelta(hours=1),
         "source": "fixture", "evidence_json": "{}"},
    )
    data = DatasetSnapshot(assets, (), (), event, (), DatasetPolicy(timeframe="1h"), "fixture", relationships)
    cohort = extract_cohort(data, CohortConfig(t0, t0))
    assert [row.token_id for row in cohort] == ["ethereum:0xbase"]
    assert cohort[0].canonical_id == "ethereum:0xbase"
    assert cohort[0].provenance["market_canonical_ids"] == ("ethereum:0xpool",)
    assert data.relationships_at("ethereum:0xpool", t0) == (relationships[0],)


def test_feature_registry_carries_temporal_contract_and_rejects_future_definition():
    cohort = extract_cohort(snapshot(), CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    registry = FeatureRegistry()
    registry.register(FeatureDefinition("liquidity", ("event.reserve_usd",), "t0", timedelta(0), compute=lambda row, bars: row.liquidity_usd))
    row = compute_features(snapshot(), cohort, registry)[0]
    assert row["liquidity"] == 12000
    assert row["feature_provenance"]["liquidity"]["missing_value_policy"] == "unknown"
    bad = FeatureRegistry()
    bad.register(FeatureDefinition("future", ("future.column",), "future", timedelta(0)))
    with pytest.raises(ValueError, match="effective timestamp"):
        compute_features(snapshot(), cohort, bad)


def test_feature_factories_preserve_launch_liquidity_and_include_both_lookback_endpoints():
    data = snapshot()
    t0 = datetime(2025, 1, 1, 2)
    member = type("Member", (), {
        "token_id": "ethereum:0xaaa", "canonical_id": "ethereum:0xaaa",
        "t0": t0, "liquidity_usd": 12_000,
    })()
    registry = FeatureRegistry()
    registry.register(launch_liquidity_feature())
    registry.register(close_return_feature(timedelta(hours=2)))

    row = compute_features(data, (member,), registry)[0]

    assert row["launch_liquidity_usd"] == 12_000
    assert row["lookback_return"] == pytest.approx(__import__("math").log(12 / 10))
    assert row["feature_provenance"]["lookback_return"]["observation_count"] == 3


@pytest.mark.parametrize(
    ("missing_value_policy", "expected", "rejected"),
    [("unknown", None, False), ("zero", 0.0, False), ("reject", None, True)],
)
def test_launch_liquidity_feature_preserves_unknown_values_by_policy(missing_value_policy, expected, rejected):
    member = type("Member", (), {
        "token_id": "ethereum:0xaaa", "canonical_id": "ethereum:0xaaa",
        "t0": datetime(2025, 1, 1), "liquidity_usd": None,
    })()
    definition = replace(launch_liquidity_feature(), missing_value_policy=missing_value_policy)

    registry = FeatureRegistry()
    registry.register(definition)
    values = compute_features(snapshot(), (member,), registry)[0]
    assert values["launch_liquidity_usd"] == expected
    assert ("launch_liquidity_usd" in values.get("rejected_features", [])) is rejected


def test_close_return_feature_keeps_custom_name_and_uses_valid_observations():
    definition = close_return_feature(timedelta(hours=3), name="custom_return")
    bars = (
        Bar("ethereum:0xaaa", datetime(2025, 1, 1), 10, 10, 10, 10, 1, "1h", "fixture"),
        Bar("ethereum:0xaaa", datetime(2025, 1, 1, 1), "invalid", "invalid", "invalid", "invalid", 1, "1h", "fixture"),
        Bar("ethereum:0xaaa", datetime(2025, 1, 1, 2), 20, 20, 20, 20, 1, "1h", "fixture"),
    )

    assert definition.name == "custom_return"
    assert definition.compute(None, bars) == pytest.approx(__import__("math").log(2))


@pytest.mark.parametrize("close", [None, "not-a-number", 0, -1])
def test_close_return_feature_ignores_invalid_and_non_positive_closes(close):
    definition = close_return_feature(timedelta(hours=2))
    bars = (
        Bar("ethereum:0xaaa", datetime(2025, 1, 1), close, close, close, close, 1, "1h", "fixture"),
        Bar("ethereum:0xaaa", datetime(2025, 1, 1, 1), 10, 10, 10, 10, 1, "1h", "fixture"),
    )

    assert definition.compute(None, bars) is None


def test_close_return_feature_requires_two_valid_bars_and_preserves_log_direction():
    definition = close_return_feature(timedelta(hours=3))
    bars = (
        Bar("ethereum:0xaaa", datetime(2025, 1, 1), 10, 10, 10, 10, 1, "1h", "fixture"),
        Bar("ethereum:0xaaa", datetime(2025, 1, 1, 1), 0, 0, 0, 0, 1, "1h", "fixture"),
        Bar("ethereum:0xaaa", datetime(2025, 1, 1, 2), 5, 5, 5, 5, 1, "1h", "fixture"),
    )

    assert definition.compute(None, bars) == pytest.approx(__import__("math").log(5 / 10))


def test_events_at_matches_canonical_identity_and_excludes_future_or_other_assets():
    t0 = datetime(2025, 1, 1)
    assets = (
        Asset("ethereum:0xaaa", "dex", "ethereum", "SAME", t0, "0xaaa"),
        Asset("solana:SAME", "dex", "solana", "SAME", t0, "SAME"),
    )
    events = (
        {"canonical_id": "ethereum:0xaaa", "event_type": "at-boundary", "timestamp": t0,
         "payload_json": {}, "source": "fixture"},
        {"canonical_id": "ethereum:0xaaa", "event_type": "future", "timestamp": t0 + timedelta(seconds=1),
         "payload_json": {}, "source": "fixture"},
        {"canonical_id": "solana:SAME", "event_type": "other-identity", "timestamp": t0,
         "payload_json": {}, "source": "fixture"},
    )
    data = DatasetSnapshot(assets, (), (), events, (), DatasetPolicy(), "events-fixture")

    assert data.events_at("ethereum:0xaaa", t0) == (events[0],)
    assert data.events_at("ethereum:SAME", t0) == ()


def test_events_at_returns_deterministic_time_order_for_unsorted_input():
    t0 = datetime(2025, 1, 1)
    assets = (Asset("ethereum:0xaaa", "dex", "ethereum", "0xaaa", t0, "0xaaa"),)
    later = {"canonical_id": "ethereum:0xaaa", "event_type": "later", "timestamp": t0 + timedelta(hours=1),
             "payload_json": {}, "source": "fixture"}
    earlier = {"canonical_id": "ethereum:0xaaa", "event_type": "earlier", "timestamp": t0,
               "payload_json": {}, "source": "fixture"}
    data = DatasetSnapshot(assets, (), (), (later, earlier), (), DatasetPolicy(), "ordered-events")

    assert data.events_at("ethereum:0xaaa", t0 + timedelta(hours=1)) == (earlier, later)


def test_labels_use_fixed_horizon_and_report_right_censoring():
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    label = generate_labels(data, cohort, LabelDefinition("return_1h", "1h"))[0]
    assert label.status == "COMPLETE"
    assert label.value == pytest.approx(__import__("math").log(11 / 10))
    assert label.provenance["quote_currency"] == "USD"
    assert HORIZONS["7d"][1] == timedelta(hours=2)


def test_split_is_chronological_sealed_and_corrections_are_recorded():
    class Row:
        def __init__(self, i): self.t0 = datetime(2025, 1, 1) + timedelta(days=i * 10); self.token_id = str(i)
    rows = tuple(Row(i) for i in range(10))
    split = build_split(rows, label_horizon=timedelta(days=1))
    assert split.discovery == tuple(str(i) for i in range(6))
    assert split.validation == ("7",) and split.holdout == ("9",) and split.sealed
    assert [row["reason"] for row in split.removed] == ["EMBARGO", "EMBARGO"]
    assert build_split(rows, embargo_days=0, label_horizon=timedelta(days=1)).validation == ("6", "7")
    assert split.as_dict() == build_split(rows, label_horizon=timedelta(days=1)).as_dict()
    hs = [Hypothesis("e", "f", (), None, "1h", None, "baseline", "2025-01-01", "d", p) for p in (.01, .02, .8)]
    assert apply_bh_fdr(hs)[0].adjusted_value == pytest.approx(.03)
    assert apply_holm(hs)[0].adjusted_value == pytest.approx(.03)


def test_bh_and_holm_denominator_is_the_declared_family_not_the_available_evidence():
    """A sibling hypothesis with no raw p-value must not shrink the correction
    burden for the hypotheses that do have evidence -- otherwise a caller could
    evade multiple-testing correction simply by omitting sibling evidence."""
    complete = [Hypothesis("e", "f", (), None, "24h", None, "m", "2025-01-01", "d", p)
                for p in (.04, .9)]
    missing = [Hypothesis("e", "f", (), None, "24h", None, "m", "2025-01-01", "d", p)
               for p in (.04, None)]
    complete_bh, missing_bh = apply_bh_fdr(complete), apply_bh_fdr(missing)
    assert missing_bh[0].adjusted_value == pytest.approx(complete_bh[0].adjusted_value)
    assert missing_bh[0].decision == complete_bh[0].decision == "rejected"
    assert missing_bh[1].adjusted_value is None
    complete_holm, missing_holm = apply_holm(complete), apply_holm(missing)
    assert missing_holm[0].adjusted_value == pytest.approx(complete_holm[0].adjusted_value)
    assert missing_holm[0].decision == complete_holm[0].decision == "rejected"
    assert missing_holm[1].adjusted_value is None


def test_split_purges_feature_and_label_windows_at_fixed_boundaries():
    class Row:
        def __init__(self, i):
            self.t0 = datetime(2025, 1, 1) + timedelta(days=i)
            self.token_id = str(i)

    split = build_split(tuple(Row(i) for i in range(10)), embargo_days=0,
                        feature_lookback=timedelta(days=2), label_horizon=timedelta(days=2))
    assert split.discovery == ("0", "1", "2", "3")
    assert split.validation == ()
    assert split.holdout == ()
    assert [(row["token_id"], row["reason"], row["boundary"]) for row in split.removed] == [
        ("4", "LABEL_WINDOW_OVERLAP", "discovery_validation"),
        ("5", "LABEL_WINDOW_OVERLAP", "discovery_validation"),
        ("6", "FEATURE_WINDOW_OVERLAP", "discovery_validation"),
        ("7", "FEATURE_WINDOW_OVERLAP", "discovery_validation"),
        ("8", "FEATURE_WINDOW_OVERLAP", "validation_holdout"),
        ("9", "FEATURE_WINDOW_OVERLAP", "validation_holdout"),
    ]
    assert split.boundaries[1]["first_later_token_id"] == "8"


def test_evaluation_baselines_filter_horizon_and_report_even_median_and_censoring():
    class Label:
        def __init__(self, token_id, horizon, status, value):
            self.token_id = token_id
            self.horizon = horizon
            self.status = status
            self.value = value

    labels = (
        Label("ethereum:a", "1h", "COMPLETE", .10),
        Label("ethereum:b", "1h", "COMPLETE", .30),
        Label("solana:c", "1h", "ECONOMIC_FAILURE", None),
        Label("solana:d", "1h", "RIGHT_CENSORED", None),
        Label("ethereum:e", "2h", "COMPLETE", 99),
    )

    baseline = descriptive_baseline(labels, horizon="1h")

    assert baseline["sample_count"] == 2
    assert baseline["coverage"] == .5
    assert baseline["mean_return"] == pytest.approx(.2)
    assert baseline["median_return"] == pytest.approx(.2)
    assert baseline["failure_rate"] == .25
    assert baseline["chain_breakdown"] == {"ethereum": 2}
    assert baseline["censoring"] == {
        "ECONOMIC_FAILURE": 1, "DATA_CENSORED": 0, "RIGHT_CENSORED": 1,
    }

    comparison = baseline_comparison(labels, horizon="1h", candidate_mean=.25)
    assert comparison["candidate_minus_baseline"] == pytest.approx(.05)
    assert comparison["families"]["market_chain"]["ethereum"]["mean_return"] == pytest.approx(.2)


def test_score_candidate_preserves_missingness_and_applies_turnover_costs():
    class Label:
        def __init__(self, token_id, status, value):
            self.token_id = token_id
            self.horizon = "1h"
            self.status = status
            self.value = value

    labels = (Label("ethereum:a", "COMPLETE", .10),
              Label("ethereum:b", "COMPLETE", .30),
              Label("solana:c", "DATA_CENSORED", None))
    result = score_candidate("costed", labels, horizon="1h", turnover=2.0,
                             costs=(0.0, .01), baseline_mean=.05)

    assert result.sample_size == 2
    assert result.coverage == pytest.approx(2 / 3)
    assert result.missingness == pytest.approx(1 / 3)
    assert result.mean_return == pytest.approx(.2)
    assert result.baseline_comparison["difference"] == pytest.approx(.15)
    assert result.cost_sensitivity == {"0.0": pytest.approx(.2), "0.01": pytest.approx(.18)}


def test_rank_candidates_prioritizes_governed_state_then_return_then_identity():
    class Label:
        def __init__(self, token_id, value):
            self.token_id = token_id
            self.horizon = "1h"
            self.status = "COMPLETE"
            self.value = value

    labels = tuple(Label(str(i), value) for i, value in enumerate((.1, .2, .3)))
    discovered = score_candidate("zeta", labels, horizon="1h")
    confirmed = replace(discovered, promotion=replace(discovered.promotion, state="holdout_confirmed"))
    validation = replace(discovered, promotion=replace(discovered.promotion, state="validation_confirmed"),
                         mean_return=.2)
    ranked = rank_candidates((discovered, validation, confirmed))

    assert [candidate.promotion.state for candidate in ranked] == [
        "holdout_confirmed", "validation_confirmed", "discovered",
    ]


@pytest.mark.parametrize("kwargs", [
    {"embargo_days": -1},
    {"feature_lookback": timedelta(seconds=-1)},
    {"label_horizon": timedelta(seconds=-1)},
])
def test_build_split_rejects_negative_temporal_configuration(kwargs):
    class Row:
        t0 = datetime(2025, 1, 1)
        token_id = "one"

    with pytest.raises(ValueError):
        build_split((Row(),), **kwargs)


def test_candidate_low_coverage_is_not_validated_alpha_and_handoff_is_phase2_compatible():
    class Label:
        def __init__(self, i): self.token_id = str(i); self.horizon = "1h"; self.status = "COMPLETE"; self.value = .1
    result = score_candidate("one", tuple(Label(i) for i in range(2)), horizon="1h", selected=lambda row: row.token_id == "0")
    assert result.coverage == .5 and result.validated_alpha is False
    spec = phase2_strategy_spec({"name": "one"}, dataset_identity="fixture", feature_policy="fp", split={"sealed": True})
    assert spec["execution"] == "next_bar_open" and spec["live_execution"] is False and spec["validated_alpha"] is False


def test_candidate_cannot_be_confirmed_from_coverage_alone():
    class Label:
        def __init__(self, i):
            self.token_id = str(i); self.horizon = "1h"; self.status = "COMPLETE"; self.value = .1

    candidate = score_candidate("coverage-only", tuple(Label(i) for i in range(20)), horizon="1h")
    assert candidate.coverage == 1.0
    assert candidate.promotion.state == "discovered"
    assert candidate.validated_alpha is False

    decision = evaluate_candidate_promotion(candidate, PromotionEvidence(target_stage="holdout"))
    assert decision.state == "insufficient_evidence"
    assert "MISSING_DISCOVERY_CORRECTION" in decision.reasons


def test_candidate_promotion_requires_every_stage_gate_and_is_preserved_by_registry(tmp_path):
    class Label:
        def __init__(self, i):
            self.token_id = str(i); self.horizon = "1h"; self.status = "COMPLETE"; self.value = .12

    candidate = score_candidate("governed", tuple(Label(i) for i in range(20)), horizon="1h",
                                baseline_mean=.02, turnover=1.0, costs=(.001, .005))
    evidence = PromotionEvidence(
        target_stage="holdout", discovery_adjusted_p_value=.01,
        effect_size=.10,
        validation_replicated=True, validation_semantics_frozen=True,
        holdout_adjusted_p_value=.02, baseline_superior=True,
        uncertainty_supports_effect=True, cost_sensitivity_passed=True,
    )
    promoted = replace(candidate, promotion=evaluate_candidate_promotion(candidate, evidence))
    assert promoted.promotion.state == "holdout_confirmed"
    assert promoted.validated_alpha is True
    assert evaluate_candidate_promotion(candidate, replace(evidence, target_stage="discovery")).state == "discovery_promoted"
    assert evaluate_candidate_promotion(candidate, replace(evidence, target_stage="validation")).state == "validation_confirmed"

    rejected = evaluate_candidate_promotion(candidate, replace(evidence, cost_sensitivity_passed=False))
    assert rejected.state == "rejected" and rejected.reasons == ("COST_SENSITIVITY_FAILED",)

    registry = HypothesisRegistry()
    registry.add(Hypothesis("e", "f", (), None, "1h", None, "baseline", "2025-01-01", "d", .01))
    registry.record_promotion(promoted, evidence, promoted.promotion)
    artifact = registry.as_artifact()
    assert artifact["promotions"][0]["inputs"]["target_stage"] == "holdout"
    assert artifact["promotions"][0]["candidate_inputs"]["coverage"] == 1.0
    assert artifact["promotions"][0]["decision"]["state"] == "holdout_confirmed"

    run = write_research_run(tmp_path, dataset_identity="fixture", cohort_config={},
                             candidates=(promoted,), hypotheses=registry)
    candidate_artifact = json.loads((run / "candidates.json").read_text())
    hypothesis_artifact = json.loads((run / "hypotheses.json").read_text())
    assert candidate_artifact[0]["promotion"]["inputs"]["target_stage"] == "holdout"
    assert hypothesis_artifact["promotions"][0]["inputs"] == artifact["promotions"][0]["inputs"]
    assert hypothesis_artifact["promotions"][0]["decision"]["state"] == "holdout_confirmed"


def test_candidate_promotion_rejects_non_finite_evidence_rather_than_silently_passing():
    """A NaN comparison like ``float('nan') <= 0`` or ``float('nan') > q`` is
    silently False in Python, so an unguarded positivity/threshold check on
    non-finite evidence would let it pass promotion instead of failing it.
    Every numeric gate that can receive caller-supplied evidence must reject
    non-finite values explicitly."""
    class Label:
        def __init__(self, i):
            self.token_id = str(i); self.horizon = "1h"; self.status = "COMPLETE"; self.value = .12

    candidate = score_candidate("non-finite-guard", tuple(Label(i) for i in range(20)), horizon="1h",
                                baseline_mean=.02, turnover=1.0, costs=(.001, .005))
    evidence = PromotionEvidence(
        target_stage="holdout", discovery_adjusted_p_value=.01,
        effect_size=.10,
        validation_replicated=True, validation_semantics_frozen=True,
        holdout_adjusted_p_value=.02, baseline_superior=True,
        uncertainty_supports_effect=True, cost_sensitivity_passed=True,
    )
    baseline = evaluate_candidate_promotion(candidate, evidence)
    assert baseline.state == "holdout_confirmed"

    nan_discovery = evaluate_candidate_promotion(candidate, replace(evidence, discovery_adjusted_p_value=float("nan")))
    assert nan_discovery.state == "rejected" and "DISCOVERY_CORRECTION_FAILED" in nan_discovery.reasons

    nan_holdout = evaluate_candidate_promotion(candidate, replace(evidence, holdout_adjusted_p_value=float("nan")))
    assert nan_holdout.state == "rejected" and nan_holdout.reasons == ("HOLDOUT_CORRECTION_FAILED",)

    nan_uncertainty = replace(candidate, uncertainty={**candidate.uncertainty, "ci95_low": float("nan")})
    uncertainty_decision = evaluate_candidate_promotion(nan_uncertainty, evidence)
    assert uncertainty_decision.state == "rejected"
    assert "UNCERTAINTY_EVIDENCE_NOT_POSITIVE" in uncertainty_decision.reasons

    nan_cost = replace(candidate, cost_sensitivity={
        key: float("nan") for key in candidate.cost_sensitivity})
    cost_decision = evaluate_candidate_promotion(nan_cost, evidence)
    assert cost_decision.state == "rejected"
    assert "COST_EVIDENCE_NOT_ROBUST" in cost_decision.reasons


def test_candidate_promotion_separates_practical_effect_from_uncertainty():
    class Label:
        def __init__(self, i):
            self.token_id = str(i); self.horizon = "1h"; self.status = "COMPLETE"; self.value = .12

    candidate = score_candidate("small-effect", tuple(Label(i) for i in range(20)), horizon="1h",
                                baseline_mean=.115, costs=(.001,))
    evidence = PromotionEvidence(
        target_stage="discovery", discovery_adjusted_p_value=.01, effect_size=.005,
        baseline_superior=True, uncertainty_supports_effect=True, cost_sensitivity_passed=True,
    )
    decision = evaluate_candidate_promotion(candidate, evidence)
    assert decision.state == "rejected"
    assert decision.reasons == ("PRACTICAL_EFFECT_TOO_SMALL",)

    missing = evaluate_candidate_promotion(candidate, replace(evidence, effect_size=None))
    assert missing.state == "insufficient_evidence"
    assert "MISSING_EFFECT_SIZE" in missing.reasons

    invalid = evaluate_candidate_promotion(candidate, replace(evidence, effect_size=float("nan")))
    assert invalid.state == "insufficient_evidence"
    assert "MISSING_EFFECT_SIZE" in invalid.reasons

    contradictory = evaluate_candidate_promotion(candidate, replace(evidence, effect_size=.10))
    assert contradictory.state == "rejected"
    assert contradictory.reasons == ("EFFECT_SIZE_MISMATCH",)

    threshold_boundary = replace(candidate, baseline_comparison={"difference": .0099999999995})
    boundary = evaluate_candidate_promotion(threshold_boundary,
                                            replace(evidence, effect_size=.0100000000004))
    assert boundary.state == "rejected"
    assert boundary.reasons == ("PRACTICAL_EFFECT_TOO_SMALL",)

    invalid_type = evaluate_candidate_promotion(candidate, replace(evidence, effect_size=True))
    assert invalid_type.state == "insufficient_evidence"
    assert "MISSING_EFFECT_SIZE" in invalid_type.reasons


def test_promotion_policy_requires_a_positive_finite_effect_floor():
    with pytest.raises(ValueError, match="minimum effect size"):
        PromotionPolicy(minimum_effect_size=0)
    with pytest.raises(ValueError, match="minimum effect size"):
        PromotionPolicy(minimum_effect_size=float("inf"))
    with pytest.raises(ValueError, match="minimum effect size"):
        PromotionPolicy(minimum_effect_size=True)

def test_temporal_alignment_rejects_permuted_labels_and_artifacts_replay_identically(tmp_path):
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum", "solana")))
    registry = FeatureRegistry()
    registry.register(FeatureDefinition("liquidity", ("event.reserve_usd",), "t0", timedelta(0), compute=lambda row, bars: row.liquidity_usd))
    features = compute_features(data, cohort, registry)
    labels = generate_labels(data, cohort, LabelDefinition("return", "1h"))
    validate_temporal_alignment(cohort, features, labels)
    with pytest.raises(ValueError, match="permuted"):
        validate_temporal_alignment(cohort, features, (replace(labels[0], token_id="wrong"), labels[1]))
    assert descriptive_baseline(labels, horizon="1h")["horizon"] == "1h"
    candidate = score_candidate("one", labels, horizon="1h")
    assert rank_candidates((candidate,))[0].name == "one"
    first = write_research_run(tmp_path / "runs", dataset_identity=data.dataset_identity, cohort_config=CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2)), cohort=cohort, features=features, labels=labels, candidates=(candidate,))
    second = write_research_run(tmp_path / "runs", dataset_identity=data.dataset_identity, cohort_config=CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2)), cohort=cohort, features=features, labels=labels, candidates=(candidate,))
    assert first == second
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()


def test_research_run_identity_changes_when_evidence_content_changes(tmp_path):
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    first = write_research_run(tmp_path / "runs", dataset_identity=data.dataset_identity,
                               cohort_config=CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2)),
                               cohort=cohort, report="original evidence")
    changed = write_research_run(tmp_path / "runs", dataset_identity=data.dataset_identity,
                                 cohort_config=CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2)),
                                 cohort=cohort, report="changed evidence")
    assert changed != first
    assert changed.name != first.name


def test_future_source_timestamp_is_rejected_and_policy_filters_bars():
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    registry = FeatureRegistry()
    registry.register(FeatureDefinition("late", ("metadata.holder_count",), "t0", timedelta(0),
                                        source_timestamp="2025-01-01T00:01:00"))
    with pytest.raises(ValueError, match="future feature"):
        compute_features(data, cohort, registry)

    restricted = DatasetSnapshot(data.assets, data.bars, data.metadata, data.events, data.lineage,
                                 replace(data.policy, end=datetime(2025, 1, 1)), "restricted")
    assert len(restricted.bars_for("ethereum:0xaaa")) == 1


def test_symbol_only_identity_is_an_exclusion_and_late_lineage_is_invisible():
    t = datetime(2025, 1, 1)
    asset = Asset("ethereum:unknown", "dex", "ethereum", "SAME", t, None)
    event = {"canonical_id": asset.canonical_id, "event_type": "new_pool_detected", "timestamp": t,
             "payload_json": '{"reserve_usd": 20000}', "source": "fixture"}
    data = DatasetSnapshot((asset,), (), (), (event,),
                           ({"dex_canonical_id": asset.canonical_id, "cex_canonical_id": "cex:SAME",
                             "linked_at": t + timedelta(hours=1)},), DatasetPolicy(), "identity-fixture")
    row = extract_cohort(data, CohortConfig(t, t))[0]
    assert row.analysis_eligible is False
    assert row.exclusion_reason == "MISSING_SOURCE_PROVENANCE"
    assert data.lineage_at(asset.canonical_id, t) == ()


def test_unavailable_quote_conversion_is_explicit_censoring():
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    labels = generate_labels(data, cohort, LabelDefinition("return", "1h"),
                             price_normalizer=lambda _bar: normalize_usd_price(1, conversion_rate=None))
    assert labels[0].status == "DATA_CENSORED" and labels[0].value is None
    comparison = baseline_comparison(labels, horizon="1h")
    assert comparison["baseline_family"] == "no_trade_unconditional"
    assert comparison["families"]["age_liquidity"]["status"] == "unavailable"
    assert comparison["families"]["momentum"]["status"] == "unavailable"


def test_phase3_labels_are_built_offline_from_persisted_dex_observations(tmp_path, monkeypatch):
    t0 = datetime(2025, 1, 1)

    class FixtureGecko:
        def new_pools(self, network):
            return [{"pool_address": "pool", "created_at": t0, "base_token_address": "base",
                     "quote_token_address": "usd", "dex_id": "fixture", "reserve_usd": 12000}]
        def trending_pools(self, network): return []
        def pool_ohlcv(self, network, address, **kwargs):
            return [{"timestamp": t0 + timedelta(minutes=minute), "open": 1 + minute / 60,
                     "high": 1 + minute / 60, "low": 1 + minute / 60,
                     "close": 1 + minute / 60, "volume": 1} for minute in range(61)]

    db = str(tmp_path / "offline-labels.duckdb")
    poll_network({"name": "ethereum"}, db_path=db, gecko=FixtureGecko(), now=t0,
                 price_config={"enabled": True, "timeframe": "minute", "aggregate": 1})
    monkeypatch.setattr("socket.socket", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("network access is forbidden")))
    data = DatasetSnapshot.from_duckdb(db, DatasetPolicy(timeframe="1m", sources=("geckoterminal",)))
    cohort = tuple(row for row in extract_cohort(data, CohortConfig(t0, t0, chains=("ethereum",)))
                   if row.token_id == "ethereum:base")
    labels = generate_labels(data, cohort, LabelDefinition("return", "1h"),
                             conversion_policy=ConversionPolicy(approved_stablecoins=("ETHEREUM:USD",)))
    assert labels[0].status == "COMPLETE"
    assert labels[0].start_price_usd == 1
    assert labels[0].end_price_usd == 2
    assert labels[0].provenance["raw_quote"] == "ethereum:usd"
def test_non_usd_labels_use_temporally_valid_conversion_provenance():
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    observations = (
        ConversionObservation("ETH", datetime(2025, 1, 1), 2_000, "local-reference"),
        ConversionObservation("ETH", datetime(2025, 1, 1, 1), 2_200, "local-reference"),
        # This later observation must never be selected for either endpoint.
        ConversionObservation("ETH", datetime(2025, 1, 1, 2), 9_999, "future-reference"),
    )
    label = generate_labels(
        data, cohort, LabelDefinition("return", "1h"),
        quote_assets={"ethereum:0xaaa": "ETH"}, conversion_observations=observations,
    )[0]

    assert label.value == pytest.approx(__import__("math").log((11 * 2_200) / (10 * 2_000)))
    assert label.provenance["raw_quote"] == "ETH"
    assert label.provenance["conversion_policy"] == "phase3-quote-usd-v1"
    assert label.provenance["start_conversion"] == {
        "quote_asset": "ETH", "conversion_rate": 2_000,
        "conversion_source": "local-reference", "conversion_time": "2025-01-01T00:00:00",
        "conversion_policy": "phase3-quote-usd-v1",
    }
    assert label.provenance["end_conversion"]["conversion_time"] == "2025-01-01T01:00:00"


def test_non_usd_quote_without_conversion_fails_closed_and_stablecoin_parity_is_explicit():
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    unavailable = generate_labels(
        data, cohort, LabelDefinition("return", "1h"),
        quote_assets={"ethereum:0xaaa": "ETH"},
    )[0]
    assert unavailable.status == "DATA_CENSORED" and unavailable.value is None
    assert unavailable.provenance["conversion_unavailable"] == "no temporally valid ETH/USD conversion"

    stable = generate_labels(
        data, cohort, LabelDefinition("return", "1h"),
        quote_assets={"ethereum:0xaaa": "USDC"},
        conversion_policy=ConversionPolicy(approved_stablecoins=("USDC",)),
    )[0]
    assert stable.status == "COMPLETE"
    assert stable.provenance["start_conversion"]["conversion_source"] == "approved_stablecoin_parity"
    assert stable.provenance["start_conversion"]["conversion_rate"] == 1.0


def test_dataset_snapshot_exposes_point_in_time_reference_series():
    t = datetime(2025, 1, 1)
    asset = (Asset("ethereum:0xaaa", "dex", "ethereum", "0xaaa", t, "0xaaa"),)
    reference_series = (
        {"series_id": "ETH/USD", "observed_at": t, "value": 2_000.0, "source": "local-reference"},
        {"series_id": "ETH/USD", "observed_at": t + timedelta(hours=1), "value": 2_200.0, "source": "local-reference"},
        {"series_id": "SOL/USD", "observed_at": t, "value": 100.0, "source": "local-reference"},
    )
    data = DatasetSnapshot(asset, (), (), (), (), DatasetPolicy(timeframe="1h"), "fixture",
                           reference_series=reference_series)
    assert [row["value"] for row in data.reference_series_at("ETH/USD", t)] == [2_000.0]
    assert {row["value"] for row in data.reference_series_at("ETH/USD", t + timedelta(hours=1))} == {2_000.0, 2_200.0}
    assert data.reference_series_at("SOL/USD", t - timedelta(seconds=1)) == ()
    assert data.reference_series_at("BTC/USD", t) == ()

    duplicate = reference_series + (reference_series[0],)
    with pytest.raises(ValueError, match="duplicate reference series observation"):
        DatasetSnapshot(asset, (), (), (), (), DatasetPolicy(timeframe="1h"), "fixture", reference_series=duplicate)


def test_generate_labels_sources_conversion_from_persisted_reference_series_without_explicit_observations():
    data = snapshot()
    cohort = extract_cohort(data, CohortConfig(datetime(2025, 1, 1), datetime(2025, 1, 2), chains=("ethereum",)))
    reference_series = (
        {"series_id": "ETH/USD", "observed_at": datetime(2025, 1, 1), "value": 2_000.0, "source": "persisted-reference"},
        {"series_id": "ETH/USD", "observed_at": datetime(2025, 1, 1, 1), "value": 2_200.0, "source": "persisted-reference"},
        # A later-observed point must never be selected for either endpoint.
        {"series_id": "ETH/USD", "observed_at": datetime(2025, 1, 1, 2), "value": 9_999.0, "source": "future-reference"},
    )
    data = DatasetSnapshot(data.assets, data.bars, data.metadata, data.events, data.lineage, data.policy,
                           data.dataset_identity, data.asset_relationships,
                           reference_series=reference_series)

    label = generate_labels(data, cohort, LabelDefinition("return", "1h"),
                            quote_assets={"ethereum:0xaaa": "ETH"})[0]

    assert label.status == "COMPLETE"
    assert label.value == pytest.approx(__import__("math").log((11 * 2_200) / (10 * 2_000)))
    assert label.provenance["start_conversion"] == {
        "quote_asset": "ETH", "conversion_rate": 2_000.0,
        "conversion_source": "persisted-reference", "conversion_time": "2025-01-01T00:00:00",
        "conversion_policy": "phase3-quote-usd-v1",
    }
    assert label.provenance["end_conversion"]["conversion_time"] == "2025-01-01T01:00:00"


def test_phase1_to_phase3_replay_uses_persisted_snapshot_and_is_deterministic(tmp_path, monkeypatch):
    """Exercise the real Phase 1 storage boundary, not only in-memory snapshots."""
    import socket

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Phase 3 attempted network access")))
    db_path = tmp_path / "phase1.duckdb"
    connection = connect(db_path)
    t0 = datetime(2025, 1, 1)
    upsert_asset({"canonical_id": "ethereum:0xaaa", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xaaa",
                  "contract_address": "0xaaa", "first_seen": t0}, connection=connection)
    insert_ohlcv_batch([
        {"canonical_id": "ethereum:0xaaa", "timestamp": t0 + timedelta(hours=i),
         "open": 10 + i, "high": 10 + i, "low": 10 + i, "close": 10 + i,
         "volume": 1, "timeframe": "1h", "source": "fixture"}
        for i in range(3)
    ], connection=connection)
    insert_event({"canonical_id": "ethereum:0xaaa", "event_type": "new_pool_detected",
                  "timestamp": t0, "payload_json": {"token_address": "0xaaa", "reserve_usd": 12_000},
                  "source": "fixture"}, connection=connection)
    connection.close()

    policy = DatasetPolicy(timeframe="1h", start=t0, end=t0 + timedelta(hours=2))
    dataset = DatasetSnapshot.from_duckdb(db_path, policy)
    config = CohortConfig(t0, t0 + timedelta(days=1), chains=("ethereum",))
    cohort = extract_cohort(dataset, config)
    registry = FeatureRegistry()
    registry.register(FeatureDefinition("liquidity", ("event.reserve_usd",), "t0", timedelta(0),
                                        compute=lambda row, bars: row.liquidity_usd))
    features = compute_features(dataset, cohort, registry)
    labels = generate_labels(dataset, cohort, LabelDefinition("return_1h", "1h"))
    validate_temporal_alignment(cohort, features, labels)
    candidate = score_candidate("liquidity", labels, horizon="1h",
                                baseline_mean=descriptive_baseline(labels, horizon="1h")["mean_return"])

    first = write_research_run(tmp_path / "runs", dataset_identity=dataset.dataset_identity,
                               cohort_config=config, cohort=cohort, features=features, labels=labels,
                               candidates=(candidate,), split=build_split(cohort).as_dict())
    second = write_research_run(tmp_path / "runs", dataset_identity=dataset.dataset_identity,
                                cohort_config=config, cohort=cohort, features=features, labels=labels,
                                candidates=(candidate,), split=build_split(cohort).as_dict())

    assert first == second
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    assert (first / "cohort.json").read_bytes() == (second / "cohort.json").read_bytes()
    assert json.loads((first / "cohort.json").read_text(encoding="utf-8"))[0]["provenance"]["dataset_identity"] == dataset.dataset_identity
