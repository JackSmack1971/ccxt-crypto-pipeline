import json
import hashlib
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from reporting.package import build_approved_handoff, generate_package
from analysis.alpha import (CohortConfig, FeatureDefinition, FeatureRegistry, LabelDefinition,
                            PromotionEvidence, build_split, compute_features,
                            evaluate_candidate_promotion, extract_cohort, generate_labels,
                            score_candidate, write_research_run)
from analysis.datasets import DatasetPolicy, DatasetSnapshot
from storage.db import connect, insert_event, insert_ohlcv_batch, upsert_asset


def approved_input(tmp_path, *, value=1.5, missing=False):
    results = json.dumps([{"time": 1, "return": None if missing else value}])
    research_dir = tmp_path / "research-run"
    research_dir.mkdir(exist_ok=True)
    (research_dir / "results.json").write_text(results, encoding="utf-8")
    result_hash = hashlib.sha256(results.encode()).hexdigest()
    research_manifest = {"manifest_version": "phase3-v1", "run_id": "fixture-research-run",
                         "immutable": True, "inputs": {"dataset_identity": "fixture-dataset"},
                         "artifacts": {"results.json": result_hash}}
    research_bytes = json.dumps(research_manifest, sort_keys=True, separators=(",", ":")).encode()
    (research_dir / "manifest.json").write_bytes(research_bytes)
    claim = {"id": "return", "text": "Return unavailable." if missing else "The observed return was 1.5%.",
             "evidence": [{"artifact": "results", "row": 0, "dataset_identity": "fixture-dataset",
                           "query_config_identity": "fixture-config",
                           "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
                           "uncertainty": "fixture"}]}
    if not missing:
        claim["derivation"] = {"evidence_index": 0, "source_field": "return", "operation": "identity",
                               "source_unit": "percent", "result_unit": "percent", "decimals": 1,
                               "suffix": "%", "expected": "1.5%"}
    return build_approved_handoff(research_dir, tmp_path / "handoffs", approval={
        "status": "approved", "identity": "fixture-approval", "reviewer": "fixture-reviewer",
        "approved_at": "2026-09-11T00:00:00Z", "scope": "fixture reporting"
    }, staged_artifacts={"results": "results.json"}, presentation={
        "title": "Fixture results", "dataset_identity": "fixture-dataset",
        "query_config_identity": "fixture-config", "code_version": "fixture-code",
        "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
        "claims": [claim],
        "charts": [{"id": "returns", "data_artifact": "results", "x_column": "time", "y_column": "return",
                     "x_unit": "hours", "y_unit": "percent", "missing_behavior": "explicit_state",
                     "source_attribution": "fixture result", "alt_text": "Observed return over time."}],
        "methodology": {"cohort_split": "sealed fixture", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    })


def test_phase4_replay_is_byte_identical_and_review_gated(tmp_path, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network access")))
    input_dir = approved_input(tmp_path)
    first = generate_package(input_dir, tmp_path / "out")
    second = generate_package(input_dir, tmp_path / "out")
    assert first == second
    assert (first / "package-manifest.json").read_bytes() == (second / "package-manifest.json").read_bytes()
    assert {p.relative_to(first).as_posix(): p.read_bytes() for p in first.rglob("*") if p.is_file()} == {
        p.relative_to(second).as_posix(): p.read_bytes() for p in second.rglob("*") if p.is_file()
    }
    assert json.loads((first / "review.json").read_text())['status'] == "pending"
    assert '<title>returns</title>' in (first / "charts" / "returns.svg").read_text()


def test_approved_handoff_is_deterministic_and_does_not_mutate_phase3_run(tmp_path):
    first = approved_input(tmp_path)
    original = (tmp_path / "research-run" / "manifest.json").read_bytes()
    second = approved_input(tmp_path)
    assert first == second
    assert (tmp_path / "research-run" / "manifest.json").read_bytes() == original
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["handoff_version"] == "phase4-approved-v1"
    assert manifest["approval"] == {
        "status": "approved", "identity": "fixture-approval", "reviewer": "fixture-reviewer",
        "approved_at": "2026-09-11T00:00:00Z", "scope": "fixture reporting"
    }
    assert manifest["research_run"]["run_id"] == "fixture-research-run"


def test_approved_handoff_rejects_changed_staged_artifact(tmp_path):
    approved_input(tmp_path)
    (tmp_path / "research-run" / "results.json").write_text(json.dumps([{"time": 1, "return": 8.0}]), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or changed"):
        build_approved_handoff(tmp_path / "research-run", tmp_path / "handoffs", approval={
            "status": "approved", "identity": "fixture-approval", "reviewer": "fixture-reviewer",
            "approved_at": "2026-09-11T00:00:00Z", "scope": "fixture reporting"
        }, staged_artifacts={"results": "results.json"}, presentation={"dataset_identity": "fixture-dataset"})


def test_phase4_rejects_unknown_handoff_fields(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["unexpected"] = True
    (input_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown fields"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_unresolved_numeric_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["evidence"][0]["artifact"] = "missing"
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unstaged artifact"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_numeric_claim_that_disagrees_with_evidence(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 9.0%."
    manifest["claims"][0]["derivation"]["expected"] = "9.0%"
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="declared value does not match"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_comparative_claim_derives_direction(tmp_path):
    input_dir = approved_input(tmp_path)
    results_path = input_dir / "results.json"
    results_path.write_text(json.dumps([{"time": 1, "return": 1.5, "baseline": 1.0}]))
    manifest = json.loads((input_dir / "manifest.json").read_text())
    digest = hashlib.sha256(results_path.read_bytes()).hexdigest()
    manifest["staged_tables"]["results"]["sha256"] = digest
    manifest["research_artifacts"]["results.json"]["sha256"] = digest
    research = json.loads((input_dir / "research-manifest.json").read_text())
    research["artifacts"]["results.json"] = digest
    research_bytes = json.dumps(research, sort_keys=True, separators=(",", ":")).encode()
    (input_dir / "research-manifest.json").write_bytes(research_bytes)
    manifest["research_run"]["sha256"] = hashlib.sha256(research_bytes).hexdigest()
    manifest["claims"][0]["text"] = "The observed return was higher than the baseline."
    manifest["claims"][0]["derivation"].update(
        operation="compare", baseline_field="baseline", suffix="", expected="higher")
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    package = generate_package(input_dir, tmp_path / "out")
    ledger = json.loads((package / "claim-ledger.json").read_text())
    assert ledger[0]["derivation"]["rendered_value"] == "higher"


def test_phase4_chart_semantics_fail_closed_and_identity_is_retained(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["transformations"] = ["identity"]
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    package = generate_package(input_dir, tmp_path / "out")
    specs = json.loads((package / "chart-specs.json").read_text())
    assert specs[0]["transformations"] == ["identity"]

    manifest["charts"][0]["transformations"] = ["rolling_average"]
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported transformation"):
        generate_package(input_dir, tmp_path / "other-out")

    manifest["charts"][0]["transformations"] = []
    manifest["charts"][0]["annotations"] = [{"kind": "line", "value": 0}]
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported annotation"):
        generate_package(input_dir, tmp_path / "annotation-out")


def test_phase4_missing_chart_values_are_explicit_not_zero(tmp_path):
    input_dir = approved_input(tmp_path, missing=True)
    package = generate_package(input_dir, tmp_path / "out")
    svg = (package / "charts" / "returns.svg").read_text()
    assert "No supported observations" in svg
    assert ">0<" not in svg


def test_phase4_rejects_changed_staged_content(tmp_path):
    input_dir = approved_input(tmp_path)
    (input_dir / "results.json").write_text(json.dumps([{"time": 1, "return": 9.0}]), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_claim_with_mismatched_dataset_identity(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["evidence"][0]["dataset_identity"] = "other-dataset"
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="mismatched dataset identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_changed_research_manifest(tmp_path):
    input_dir = approved_input(tmp_path)
    (input_dir / "research-manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="research manifest content hash mismatch"):
        generate_package(input_dir, tmp_path / "out")


def test_phase3_artifact_is_accepted_only_through_explicit_approved_handoff(tmp_path):
    research_dir = write_research_run(
        tmp_path / "research", dataset_identity="fixture-dataset", cohort_config={"split": "sealed"},
        labels=({"token_id": "ethereum:0xaaa", "horizon": "1h", "value": 0.1},),
        report="descriptive research only")
    research_manifest_path = research_dir / "manifest.json"
    research_manifest = json.loads(research_manifest_path.read_text(encoding="utf-8"))
    labels_path = research_dir / "labels.json"
    labels_hash = research_manifest["artifacts"]["labels.json"]
    relative_manifest = research_manifest_path.relative_to(tmp_path).as_posix()
    relative_labels = labels_path.relative_to(tmp_path).as_posix()
    manifest = {
        "manifest_identity": "approved-fixture-handoff", "approved": True, "immutable": True,
        "approval": {"status": "approved", "reviewer": "fixture-reviewer"},
        "title": "Approved Phase 3 handoff", "dataset_identity": "fixture-dataset",
        "query_config_identity": "fixture-config", "code_version": "fixture-code",
        "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
        "research_run": {"path": relative_manifest, "sha256": hashlib.sha256(research_manifest_path.read_bytes()).hexdigest()},
        "research_artifacts": {"labels.json": {"path": relative_labels, "sha256": labels_hash}},
        "staged_tables": {"results": {"path": relative_labels, "sha256": labels_hash}},
        "claims": [{"id": "return", "text": "The observed return was 0.1.", "evidence": [{
            "artifact": "results", "row": 0, "dataset_identity": "fixture-dataset",
            "query_config_identity": "fixture-config", "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
            "uncertainty": "fixture"}], "derivation": {
                "evidence_index": 0, "source_field": "value", "operation": "identity",
                "source_unit": "log-return", "result_unit": "log-return", "decimals": 1,
                "expected": "0.1"}}],
        "charts": [{"id": "returns", "data_artifact": "results", "x_column": "horizon", "y_column": "value",
                     "x_unit": "label", "y_unit": "log-return", "missing_behavior": "explicit_state",
                     "source_attribution": "approved Phase 3 result", "alt_text": "Observed return label."}],
        "methodology": {"cohort_split": "sealed", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    package = generate_package(tmp_path, tmp_path / "out")
    package_manifest = json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))
    assert package_manifest["inputs"]["research_run_id"] == research_manifest["run_id"]


def test_offline_phase1_to_phase4_chain_is_content_addressed_and_review_gated(tmp_path, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("offline research/reporting attempted network access")))
    t0 = datetime(2025, 1, 1)
    db_path = tmp_path / "phase1.duckdb"
    connection = connect(db_path)
    upsert_asset({"canonical_id": "ethereum:0xaaa", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xaaa",
                  "contract_address": "0xaaa", "first_seen": t0}, connection=connection)
    insert_ohlcv_batch([{"canonical_id": "ethereum:0xaaa", "timestamp": t0 + timedelta(hours=i),
                         "open": 10 + i, "high": 10 + i, "low": 10 + i, "close": 10 + i,
                         "volume": 1, "timeframe": "1h", "source": "fixture"}
                        for i in range(2)], connection=connection)
    insert_event({"canonical_id": "ethereum:0xaaa", "event_type": "new_pool_detected", "timestamp": t0,
                  "payload_json": {"token_address": "0xaaa", "reserve_usd": 12_000}, "source": "fixture"},
                 connection=connection)
    connection.close()

    dataset = DatasetSnapshot.from_duckdb(db_path, DatasetPolicy(timeframe="1h", start=t0, end=t0 + timedelta(hours=1)))
    cohort_config = CohortConfig(t0, t0 + timedelta(days=1), chains=("ethereum",))
    cohort = extract_cohort(dataset, cohort_config)
    registry = FeatureRegistry()
    registry.register(FeatureDefinition(
        "launch_liquidity_usd", ("event.reserve_usd",), "t0", timedelta(0),
        compute=lambda row, _bars: row.liquidity_usd,
    ))
    features = compute_features(dataset, cohort, registry)
    labels = generate_labels(dataset, cohort, LabelDefinition("return_1h", "1h"))
    candidate = score_candidate("baseline", labels, horizon="1h")
    candidate = replace(candidate, promotion=evaluate_candidate_promotion(
        candidate, PromotionEvidence(target_stage="holdout")))
    assert candidate.promotion.state == "insufficient_coverage"
    research_dir = write_research_run(tmp_path / "research", dataset_identity=dataset.dataset_identity,
                                      cohort_config=cohort_config, cohort=cohort, features=features, labels=labels,
                                      candidates=(candidate,), split=build_split(cohort).as_dict())
    research_manifest = json.loads((research_dir / "manifest.json").read_text(encoding="utf-8"))
    time_range = {"start": t0.isoformat(), "end": (t0 + timedelta(hours=1)).isoformat()}
    handoff = build_approved_handoff(research_dir, tmp_path / "handoffs", approval={
        "status": "approved", "identity": "phase1-to-phase4-fixture",
        "reviewer": "fixture-reviewer", "approved_at": "2026-09-11T00:00:00Z",
        "scope": "offline closure fixture",
    }, staged_artifacts={"labels": "labels.json"}, presentation={
        "title": "Offline approved research", "dataset_identity": dataset.dataset_identity,
        "query_config_identity": "fixture-phase4-config", "code_version": "fixture-code",
        "time_range": time_range,
        "claims": [{"id": "label", "text": f"The observed return was {labels[0].value:.12f}.", "evidence": [{
            "artifact": "labels", "row": 0, "dataset_identity": dataset.dataset_identity,
            "query_config_identity": "fixture-phase4-config", "time_range": time_range,
            "uncertainty": "fixture"}], "derivation": {
                "evidence_index": 0, "source_field": "value", "operation": "identity",
                "source_unit": "log-return", "result_unit": "log-return", "decimals": 12,
                "expected": f"{labels[0].value:.12f}"}}],
        "charts": [{"id": "label", "data_artifact": "labels", "x_column": "value", "y_column": "value",
                     "x_unit": "log-return", "y_unit": "log-return", "missing_behavior": "explicit_state",
                     "source_attribution": "approved Phase 3 result", "alt_text": "Observed one-hour return."}],
        "methodology": {"cohort_split": "sealed fixture", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    })
    package = generate_package(handoff, tmp_path / "out")
    assert json.loads((package / "review.json").read_text(encoding="utf-8"))["status"] == "pending"
    assert json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))["inputs"]["research_run_id"] == research_manifest["run_id"]
    assert json.loads((research_dir / "features.json").read_text(encoding="utf-8"))[0]["launch_liquidity_usd"] == 12_000
    assert json.loads((research_dir / "candidates.json").read_text(encoding="utf-8"))[0]["promotion"]["state"] == "insufficient_coverage"


def test_phase4_requires_approval_and_scans_secrets(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["approved"] = False
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved manifest"):
        generate_package(input_dir, tmp_path / "out")

    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["approved"] = True
    manifest["claims"][0]["text"] = "The api_key=sk-1234567890abcdef must not be emitted."
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="secret"):
        generate_package(input_dir, tmp_path / "out")
