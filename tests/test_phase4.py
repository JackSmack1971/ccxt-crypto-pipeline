import json
import hashlib
from datetime import datetime, timedelta

import pytest

from reporting.package import generate_package
from analysis.alpha import (CohortConfig, LabelDefinition, build_split, extract_cohort,
                            generate_labels, score_candidate, write_research_run)
from analysis.datasets import DatasetPolicy, DatasetSnapshot
from storage.db import connect, insert_event, insert_ohlcv_batch, upsert_asset


def approved_input(tmp_path, *, value=1.5, missing=False):
    results = json.dumps([{"time": 1, "return": None if missing else value}])
    (tmp_path / "results.json").write_text(results, encoding="utf-8")
    result_hash = hashlib.sha256(results.encode()).hexdigest()
    research_manifest = {"manifest_version": "phase3-v1", "run_id": "fixture-research-run",
                         "immutable": True, "inputs": {"dataset_identity": "fixture-dataset"},
                         "artifacts": {"results.json": result_hash}}
    research_bytes = json.dumps(research_manifest, sort_keys=True, separators=(",", ":")).encode()
    (tmp_path / "research-manifest.json").write_bytes(research_bytes)
    manifest = {
        "manifest_identity": "fixture-manifest",
        "approved": True,
        "immutable": True,
        "title": "Fixture results",
        "dataset_identity": "fixture-dataset",
        "query_config_identity": "fixture-config",
        "code_version": "fixture-code",
        "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
        "staged_tables": {"results": {"path": "results.json", "sha256": hashlib.sha256(results.encode()).hexdigest()}},
        "research_run": {"path": "research-manifest.json", "sha256": hashlib.sha256(research_bytes).hexdigest()},
        "research_artifacts": {"results.json": {"path": "results.json", "sha256": result_hash}},
        "approval": {"status": "approved", "reviewer": "fixture-reviewer"},
        "claims": [{"id": "return", "text": "The observed return was 1.5%.", "evidence": [{
            "artifact": "results", "row": 0, "dataset_identity": "fixture-dataset",
            "query_config_identity": "fixture-config", "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
            "uncertainty": "fixture"
        }]}],
        "charts": [{"id": "returns", "data_artifact": "results", "x_column": "time", "y_column": "return",
                     "x_unit": "hours", "y_unit": "percent", "missing_behavior": "explicit_state",
                     "source_attribution": "fixture result", "alt_text": "Observed return over time."}],
        "methodology": {"cohort_split": "sealed fixture", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_phase4_replay_is_byte_identical_and_review_gated(tmp_path, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network access")))
    approved_input(tmp_path)
    first = generate_package(tmp_path, tmp_path / "out")
    second = generate_package(tmp_path, tmp_path / "out")
    assert first == second
    assert (first / "package-manifest.json").read_bytes() == (second / "package-manifest.json").read_bytes()
    assert {p.relative_to(first).as_posix(): p.read_bytes() for p in first.rglob("*") if p.is_file()} == {
        p.relative_to(second).as_posix(): p.read_bytes() for p in second.rglob("*") if p.is_file()
    }
    assert json.loads((first / "review.json").read_text())['status'] == "pending"
    assert '<title>returns</title>' in (first / "charts" / "returns.svg").read_text()


def test_phase4_rejects_unresolved_numeric_claim(tmp_path):
    approved_input(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["claims"][0]["evidence"][0]["artifact"] = "missing"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unstaged artifact"):
        generate_package(tmp_path, tmp_path / "out")


def test_phase4_missing_chart_values_are_explicit_not_zero(tmp_path):
    approved_input(tmp_path, missing=True)
    package = generate_package(tmp_path, tmp_path / "out")
    svg = (package / "charts" / "returns.svg").read_text()
    assert "No supported observations" in svg
    assert ">0<" not in svg


def test_phase4_rejects_changed_staged_content(tmp_path):
    approved_input(tmp_path)
    (tmp_path / "results.json").write_text(json.dumps([{"time": 1, "return": 9.0}]), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        generate_package(tmp_path, tmp_path / "out")


def test_phase4_rejects_claim_with_mismatched_dataset_identity(tmp_path):
    approved_input(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["claims"][0]["evidence"][0]["dataset_identity"] = "other-dataset"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="mismatched dataset identity"):
        generate_package(tmp_path, tmp_path / "out")


def test_phase4_rejects_changed_research_manifest(tmp_path):
    approved_input(tmp_path)
    (tmp_path / "research-manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="research manifest content hash mismatch"):
        generate_package(tmp_path, tmp_path / "out")


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
            "uncertainty": "fixture"}]}],
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
    labels = generate_labels(dataset, cohort, LabelDefinition("return_1h", "1h"))
    candidate = score_candidate("baseline", labels, horizon="1h")
    research_dir = write_research_run(tmp_path / "research", dataset_identity=dataset.dataset_identity,
                                      cohort_config=cohort_config, cohort=cohort, labels=labels,
                                      candidates=(candidate,), split=build_split(cohort).as_dict())
    research_manifest_path = research_dir / "manifest.json"
    research_manifest = json.loads(research_manifest_path.read_text(encoding="utf-8"))
    labels_path = research_dir / "labels.json"
    labels_hash = research_manifest["artifacts"]["labels.json"]
    relative_manifest = research_manifest_path.relative_to(tmp_path).as_posix()
    relative_labels = labels_path.relative_to(tmp_path).as_posix()
    time_range = {"start": t0.isoformat(), "end": (t0 + timedelta(hours=1)).isoformat()}
    manifest = {
        "manifest_identity": "phase1-to-phase4-fixture", "approved": True, "immutable": True,
        "approval": {"status": "approved", "reviewer": "fixture-reviewer"},
        "title": "Offline approved research", "dataset_identity": dataset.dataset_identity,
        "query_config_identity": "fixture-phase4-config", "code_version": "fixture-code",
        "time_range": time_range,
        "research_run": {"path": relative_manifest, "sha256": hashlib.sha256(research_manifest_path.read_bytes()).hexdigest()},
        "research_artifacts": {"labels.json": {"path": relative_labels, "sha256": labels_hash}},
        "staged_tables": {"labels": {"path": relative_labels, "sha256": labels_hash}},
        "claims": [{"id": "label", "text": f"The observed return was {labels[0].value}.", "evidence": [{
            "artifact": "labels", "row": 0, "dataset_identity": dataset.dataset_identity,
            "query_config_identity": "fixture-phase4-config", "time_range": time_range,
            "uncertainty": "fixture"}]}],
        "charts": [{"id": "label", "data_artifact": "labels", "x_column": "value", "y_column": "value",
                     "x_unit": "log-return", "y_unit": "log-return", "missing_behavior": "explicit_state",
                     "source_attribution": "approved Phase 3 result", "alt_text": "Observed one-hour return."}],
        "methodology": {"cohort_split": "sealed fixture", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    package = generate_package(tmp_path, tmp_path / "out")
    assert json.loads((package / "review.json").read_text(encoding="utf-8"))["status"] == "pending"
    assert json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))["inputs"]["research_run_id"] == research_manifest["run_id"]


def test_phase4_requires_approval_and_scans_secrets(tmp_path):
    approved_input(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["approved"] = False
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved manifest"):
        generate_package(tmp_path, tmp_path / "out")

    approved_input(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The api_key=sk-1234567890abcdef must not be emitted."
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="secret"):
        generate_package(tmp_path, tmp_path / "out")
