from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from analysis.alpha import (CohortConfig, FeatureDefinition, FeatureRegistry, HORIZONS,
                            Hypothesis, LabelDefinition, apply_bh_fdr, apply_holm,
                            build_split, compute_features, extract_cohort, generate_labels, normalize_usd_price,
                            descriptive_baseline, phase2_strategy_spec, rank_candidates, score_candidate, write_research_run,
                            validate_temporal_alignment, baseline_comparison)
from analysis.datasets import Asset, Bar, DatasetPolicy, DatasetSnapshot


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
        def __init__(self, i): self.t0 = datetime(2025, 1, 1) + timedelta(days=i); self.token_id = str(i)
    split = build_split(tuple(Row(i) for i in range(10)))
    assert len(split.discovery) == 6 and len(split.validation) == 2 and len(split.holdout) == 2 and split.sealed
    hs = [Hypothesis("e", "f", (), None, "1h", None, "baseline", "2025-01-01", "d", p) for p in (.01, .02, .8)]
    assert apply_bh_fdr(hs)[0].adjusted_value == pytest.approx(.03)
    assert apply_holm(hs)[0].adjusted_value == pytest.approx(.03)


def test_candidate_low_coverage_is_not_validated_alpha_and_handoff_is_phase2_compatible():
    class Label:
        def __init__(self, i): self.token_id = str(i); self.horizon = "1h"; self.status = "COMPLETE"; self.value = .1
    result = score_candidate("one", tuple(Label(i) for i in range(2)), horizon="1h", selected=lambda row: row.token_id == "0")
    assert result.coverage == .5 and result.validated_alpha is False
    spec = phase2_strategy_spec({"name": "one"}, dataset_identity="fixture", feature_policy="fp", split={"sealed": True})
    assert spec["execution"] == "next_bar_open" and spec["live_execution"] is False and spec["validated_alpha"] is False

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
