import json
import hashlib
from datetime import datetime, timedelta

import pytest

from reporting.package import build_approved_handoff, generate_package
from reporting.package.handoff import _dump
from reporting.render.static import render_svg
from analysis.alpha import (CohortConfig, LabelDefinition, build_split, extract_cohort,
                            generate_labels, score_candidate, write_research_run)
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
    return build_approved_handoff(research_dir, tmp_path / "handoffs", approval={
        "status": "approved", "identity": "fixture-approval", "reviewer": "fixture-reviewer",
        "approved_at": "2026-09-11T00:00:00Z", "scope": "fixture reporting"
    }, staged_artifacts={"results": "results.json"}, presentation={
        "title": "Fixture results", "dataset_identity": "fixture-dataset",
        "query_config_identity": "fixture-config", "code_version": "fixture-code",
        "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
        "claims": [{"id": "return", "text": "The observed return was " + ("unavailable." if missing else "1.5%"), "evidence": [{
            "artifact": "results", "row": 0, "dataset_identity": "fixture-dataset",
            "query_config_identity": "fixture-config", "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
            "uncertainty": "fixture"
        }], "derivation": {"source_field": "return", "operation": "identity", "unit": "percent", "source_unit": "percent", "decimals": 1}}],
        "charts": [{"id": "returns", "data_artifact": "results", "x_column": "time", "y_column": "return",
                     "x_unit": "hours", "y_unit": "percent", "missing_behavior": "explicit_state",
                     "source_attribution": "fixture result", "alt_text": "Observed return over time."}],
        "methodology": {"cohort_split": "sealed fixture", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    })


def rekey_handoff(manifest):
    presentation = {key: manifest[key] for key in {
        "title", "dataset_identity", "query_config_identity", "config_identity", "code_version",
        "time_range", "claims", "charts", "methodology", "approved_chart_transformations"
    } if key in manifest}
    target = {"research_run_id": manifest["research_run"]["run_id"],
              "research_manifest_sha256": manifest["research_run"]["sha256"],
              "approval": manifest["approval"],
              "staged_artifacts": {key: manifest["staged_tables"][key]["path"]
                                   for key in sorted(manifest["staged_tables"])},
              "presentation": presentation}
    manifest["handoff_id"] = hashlib.sha256(_dump(target)).hexdigest()[:24]


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


def test_approved_handoff_rejects_escaping_artifact_name(tmp_path):
    approved_input(tmp_path)
    with pytest.raises(ValueError, match="safe relative path"):
        build_approved_handoff(tmp_path / "research-run", tmp_path / "handoffs", approval={
            "status": "approved", "identity": "fixture-approval", "reviewer": "fixture-reviewer",
            "approved_at": "2026-09-11T00:00:00Z", "scope": "fixture reporting"
        }, staged_artifacts={"results": "../results.json"}, presentation={"dataset_identity": "fixture-dataset"})


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
    rekey_handoff(manifest); (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unstaged artifact"):
        generate_package(input_dir, tmp_path / "out")


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
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_claim_when_rendered_number_disagrees_with_evidence(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 9.9%."
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_requires_derivation_for_numeric_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0].pop("derivation")
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_requires_evidence_for_factual_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0] = {"id": "fact", "text": "The cohort was sealed.", "kind": "fact"}
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_unsupported_chart_transformation(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["transformations"] = ["interpolate"]
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_escaping_and_duplicate_chart_ids(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["id"] = "../../escaped"
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="safe relative filename"):
        generate_package(input_dir, tmp_path / "out")

    duplicate_root = tmp_path / "duplicate"
    duplicate_root.mkdir()
    input_dir = approved_input(duplicate_root)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"].append(dict(manifest["charts"][0]))
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="chart ids must be unique"):
        generate_package(input_dir, tmp_path / "duplicate-out")


def test_phase4_requires_result_approval_for_supported_chart_transformation(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["transformations"] = ["sort_x"]
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_direct_manifest_cannot_self_authorize_chart_transformation(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest.pop("handoff_version", None)
    manifest["charts"][0]["transformations"] = ["sort_x"]
    manifest["approved_chart_transformations"] = {"returns": ["sort_x"]}
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported or mutable approved handoff"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_extra_number_in_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 1.5% versus 0.5%."
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_claim_with_wrong_unit_text(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 1.5 dollars."
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_reversed_comparative_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 1.5% lower."
    manifest["claims"][0]["derivation"] = {"source_field": "return", "operation": "identity", "unit": "percent", "decimals": 1}
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_untyped_exceeded_comparison(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "A exceeded B by 1.0%."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="comparative derivation requires two evidence rows"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_executes_declared_chart_annotation(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["annotations"] = [{"type": "horizontal_line", "value": 1.5, "label": "baseline", "source": "fixture result",
                                               "evidence": {"artifact": "results", "row": 0, "field": "return",
                                                             "dataset_identity": "fixture-dataset", "query_config_identity": "fixture-config",
                                                             "time_range": {"start": "2025-01-01", "end": "2025-01-02"}, "uncertainty": "fixture", "unit": "percent"}}]
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    package = generate_package(input_dir, tmp_path / "out")
    svg = (package / "charts" / "returns.svg").read_text()
    assert "baseline" in svg and "stroke-dasharray" in svg


def test_phase4_rejects_unsupported_chart_annotation(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["annotations"] = [{"type": "fake", "value": 1, "label": "ignored"}]
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_unknown_or_invisible_chart_annotation(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["annotations"] = [{"type": "horizontal_line", "value": 1.5, "label": "baseline",
                                               "source": "fixture", "color": "red", "evidence": {}}]
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported annotation fields"):
        generate_package(input_dir, tmp_path / "out")

    with pytest.raises(ValueError, match="visible y range"):
        render_svg({"id": "returns", "x_column": "time", "y_column": "return", "x_unit": "hours",
                    "y_unit": "percent", "missing_behavior": "explicit_state", "source_attribution": "fixture",
                    "alt_text": "Observed return.", "annotations": [{"type": "horizontal_line", "value": 100,
                    "label": "baseline", "source": "fixture"}], "width": 800, "height": 450},
                   [{"time": 1, "return": 1.5}])


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
        "handoff_version": "phase4-approved-v1", "approved": True, "immutable": True,
        "approval": {"status": "approved", "identity": "fixture-approval", "reviewer": "fixture-reviewer",
                      "approved_at": "2026-09-11T00:00:00Z", "scope": "fixture reporting"},
        "title": "Approved Phase 3 handoff", "dataset_identity": "fixture-dataset",
        "query_config_identity": "fixture-config", "code_version": "fixture-code",
        "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
        "research_run": {"path": relative_manifest, "sha256": hashlib.sha256(research_manifest_path.read_bytes()).hexdigest(), "run_id": research_manifest["run_id"]},
        "research_artifacts": {"labels.json": {"path": relative_labels, "sha256": labels_hash}},
        "staged_tables": {"results": {"path": relative_labels, "sha256": labels_hash}},
        "claims": [{"id": "return", "text": "The observed log-return was 0.1.", "evidence": [{
            "artifact": "results", "row": 0, "dataset_identity": "fixture-dataset",
            "query_config_identity": "fixture-config", "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
            "uncertainty": "fixture"}], "derivation": {"source_field": "value", "operation": "identity", "unit": "log-return", "source_unit": "log-return", "decimals": 1}}],
        "charts": [{"id": "returns", "data_artifact": "results", "x_column": "horizon", "y_column": "value",
                     "x_unit": "label", "y_unit": "log-return", "missing_behavior": "explicit_state",
                     "source_attribution": "approved Phase 3 result", "alt_text": "Observed return label."}],
        "methodology": {"cohort_split": "sealed", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    }
    rekey_handoff(manifest)
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
        "handoff_version": "phase4-approved-v1", "approved": True, "immutable": True,
        "approval": {"status": "approved", "identity": "fixture-approval", "reviewer": "fixture-reviewer",
                      "approved_at": "2026-09-11T00:00:00Z", "scope": "fixture reporting"},
        "title": "Offline approved research", "dataset_identity": dataset.dataset_identity,
        "query_config_identity": "fixture-phase4-config", "code_version": "fixture-code",
        "time_range": time_range,
        "research_run": {"path": relative_manifest, "sha256": hashlib.sha256(research_manifest_path.read_bytes()).hexdigest(), "run_id": research_manifest["run_id"]},
        "research_artifacts": {"labels.json": {"path": relative_labels, "sha256": labels_hash}},
        "staged_tables": {"labels": {"path": relative_labels, "sha256": labels_hash}},
        "claims": [{"id": "label", "text": f"The observed log-return was {labels[0].value:.6f}.", "evidence": [{
            "artifact": "labels", "row": 0, "dataset_identity": dataset.dataset_identity,
            "query_config_identity": "fixture-phase4-config", "time_range": time_range,
            "uncertainty": "fixture"}], "derivation": {"source_field": "value", "operation": "identity", "unit": "log-return", "source_unit": "log-return", "decimals": 6}}],
        "charts": [{"id": "label", "data_artifact": "labels", "x_column": "value", "y_column": "value",
                     "x_unit": "log-return", "y_unit": "log-return", "missing_behavior": "explicit_state",
                     "source_attribution": "approved Phase 3 result", "alt_text": "Observed one-hour return."}],
        "methodology": {"cohort_split": "sealed fixture", "costs": "0 bps", "missingness": "reported",
                         "uncertainty": "fixture", "limitations": "not predictive"},
    }
    rekey_handoff(manifest)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    package = generate_package(tmp_path, tmp_path / "out")
    assert json.loads((package / "review.json").read_text(encoding="utf-8"))["status"] == "pending"
    assert json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))["inputs"]["research_run_id"] == research_manifest["run_id"]


def test_phase4_requires_approval_and_scans_secrets(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["approved"] = False
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff"):
        generate_package(input_dir, tmp_path / "out")

    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["approved"] = True
    manifest["claims"][0]["text"] = "The api_key=sk-1234567890abcdef must not be emitted."
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved handoff identity"):
        generate_package(input_dir, tmp_path / "out")
