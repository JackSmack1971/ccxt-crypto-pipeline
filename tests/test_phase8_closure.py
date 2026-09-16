import hashlib
import json
import re

from reporting.package import generate_package
from reporting.package.export import export_package
from reporting.package.review_history import record_review
from reporting.render.static import validate_accessibility
from test_phase4 import approved_input


def _files(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def test_phase8_publication_closure(tmp_path, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("publication closure attempted network access")))

    handoff = approved_input(tmp_path)
    package = generate_package(handoff, tmp_path / "packages")
    replay = generate_package(handoff, tmp_path / "packages")
    assert _files(package) == _files(replay)

    manifest = json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))
    ledger = json.loads((package / "claim-ledger.json").read_text(encoding="utf-8"))
    assert manifest["review_status"] == "pending"
    assert manifest["inputs"]["human_review"] == "required"
    assert manifest["inputs"]["research_run_id"] == "fixture-research-run"
    assert manifest["staged_inputs"]["results"]["sha256"] == hashlib.sha256(
        (tmp_path / "research-run" / "results.json").read_bytes()).hexdigest()
    assert ledger[0]["evidence"][0]["artifact"] == "results"
    assert ledger[0]["derivation"] == {
        "decimals": 1, "left_label": "", "operation": "identity",
        "right_label": "", "source_field": "return", "source_unit": "percent",
        "unit": "percent"}

    chart_spec = json.loads((package / "chart-specs.json").read_text(encoding="utf-8"))[0]
    svg = (package / "charts" / "returns.svg").read_text(encoding="utf-8")
    validate_accessibility(svg, chart_spec)
    assert 'meta name="review-status" content="pending"' in (
        package / "article.html").read_text(encoding="utf-8")

    history = tmp_path / "history"
    first = record_review(package, history, target_kind="package", decision="approved",
                          reviewer="First reviewer", reviewed_at="2026-09-16T12:00:00Z",
                          rationale="Initial approval.")
    effective = record_review(package, history, target_kind="package", decision="approved",
                              reviewer="Final reviewer", reviewed_at="2026-09-16T12:01:00Z",
                              rationale="Approved after closure review.",
                              supersedes_review_id=first.stem)
    exported = export_package(package, history, tmp_path / "exports")
    assert export_package(package, history, tmp_path / "exports") == exported
    export_manifest = json.loads((exported / "export-manifest.json").read_text(encoding="utf-8"))
    assert export_manifest["approvals"] == [{
        "review_id": effective.stem, "reviewer": "Final reviewer",
        "reviewed_at": "2026-09-16T12:01:00Z",
        "rationale": "Approved after closure review.", "notes": ""}]
    assert export_manifest["source_package_id"] == package.name
    for name, expected in export_manifest["files"].items():
        assert hashlib.sha256((exported / name).read_bytes()).hexdigest() == expected

    exported_bytes = b"".join(_files(exported).values())
    assert not re.search(rb"(?i)(api[_-]?key|secret|password|token)\s*[:=]", exported_bytes)
    assert not re.search(rb"(?:[A-Za-z]:\\|/(?:Users|home|tmp|var)/)", exported_bytes)
