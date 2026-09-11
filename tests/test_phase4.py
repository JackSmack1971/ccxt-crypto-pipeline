import json

import pytest

from reporting.package import generate_package


def approved_input(tmp_path, *, value=1.5, missing=False):
    (tmp_path / "results.json").write_text(json.dumps([{"time": 1, "return": None if missing else value}]), encoding="utf-8")
    manifest = {
        "manifest_identity": "fixture-manifest",
        "approved": True,
        "immutable": True,
        "title": "Fixture results",
        "dataset_identity": "fixture-dataset",
        "query_config_identity": "fixture-config",
        "code_version": "fixture-code",
        "time_range": {"start": "2025-01-01", "end": "2025-01-02"},
        "staged_tables": {"results": "results.json"},
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
