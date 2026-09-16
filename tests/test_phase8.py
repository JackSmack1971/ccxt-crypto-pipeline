import hashlib
import json
import subprocess
import sys

import pytest

from reporting.package.catalog import catalog_artifacts
from reporting.package.export import export_package
from reporting.package.draft import build_draft_request, generate_assisted_draft
from reporting.package.review_history import record_review, review_history
from test_phase6 import runner_snapshot, runner_spec
from analysis.experiments.runner import run_experiment


def _package(tmp_path):
    package = tmp_path / "package-id"
    package.mkdir(parents=True)
    artifact = b"# reviewed\n"
    (package / "article.md").write_bytes(artifact)
    ledger = b"[]\n"
    (package / "claim-ledger.json").write_bytes(ledger)
    manifest = {"package_version": "phase4-v1", "package_id": package.name,
                "immutable": True, "review_status": "pending",
                "artifacts": {"article.md": hashlib.sha256(artifact).hexdigest(),
                               "claim-ledger.json": hashlib.sha256(ledger).hexdigest()}}
    (package / "package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return package


def test_review_history_records_verified_immutable_decisions_and_supersession(tmp_path):
    package = _package(tmp_path)
    history = tmp_path / "history"
    rejected = record_review(package, history, target_kind="package", decision="rejected",
                             reviewer="Reviewer", reviewed_at="2026-09-16T12:00:00Z",
                             rationale="Needs another review.")
    approved = record_review(package, history, target_kind="package", decision="approved",
                             reviewer="Reviewer", reviewed_at="2026-09-16T12:00:30Z",
                             rationale="Approved after the follow-up review.")
    note = record_review(package, history, target_kind="package", decision="note",
                         reviewer="Reviewer", reviewed_at="2026-09-16T12:01:00Z",
                         notes="Checked the source links.")
    superseded = record_review(package, history, target_kind="package", decision="superseded",
                               reviewer="Reviewer", reviewed_at="2026-09-16T12:02:00Z",
                               rationale="Replaced by the later review.",
                               supersedes_review_id=rejected.stem)
    records = review_history(history, package.name)
    assert [item["review_id"] for item in records] == sorted(
        (rejected.stem, approved.stem, note.stem, superseded.stem))
    assert records[-1]["supersedes_review_id"] == rejected.stem
    assert records[-1]["target"]["manifest_sha256"] == hashlib.sha256(
        (package / "package-manifest.json").read_bytes()).hexdigest()

    before = superseded.read_bytes()
    assert record_review(package, history, target_kind="package", decision="superseded",
                         reviewer="Reviewer", reviewed_at="2026-09-16T12:02:00Z",
                         rationale="Replaced by the later review.",
                         supersedes_review_id=rejected.stem).read_bytes() == before


def test_review_history_fails_closed_for_unverified_or_invalid_reviews(tmp_path):
    package = _package(tmp_path)
    (package / "article.md").write_bytes(b"tampered\n")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        record_review(package, tmp_path / "history", target_kind="package", decision="approved",
                      reviewer="Reviewer", reviewed_at="2026-09-16T12:00:00Z", rationale="Approved.")

    package = _package(tmp_path / "second")
    with pytest.raises(ValueError, match="supersedes_review_id"):
        record_review(package, tmp_path / "history", target_kind="package", decision="superseded",
                      reviewer="Reviewer", reviewed_at="2026-09-16T12:00:00Z", rationale="Replaced.")


def test_catalog_verifies_and_searches_research_runs_and_packages_without_writing(tmp_path):
    runs = tmp_path / "runs"
    run = run_experiment(runner_spec(), runner_snapshot(), runs)
    package = _package(tmp_path / "packages")
    # The package helper intentionally uses a compact valid manifest; the catalog
    # only needs to verify its immutable artifact contract.
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    records = catalog_artifacts(research_root=runs, package_root=package.parent,
                                query="fixture")
    assert [(item.kind, item.artifact_id) for item in records] == [("research_run", run.name)]
    all_records = catalog_artifacts(research_root=runs, package_root=package.parent)
    assert {item.kind for item in all_records} == {"research_run", "package"}
    assert all_records == catalog_artifacts(research_root=runs, package_root=package.parent)
    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert before == after


def test_catalog_rejects_tampered_package_and_cli_returns_metadata(tmp_path):
    package = _package(tmp_path / "packages")
    output = subprocess.run(
        [sys.executable, "-m", "reporting.package", "catalog", "--package-root", str(package.parent),
         "--query", package.name], capture_output=True, text=True, check=True,
    )
    assert json.loads(output.stdout)[0]["artifact_id"] == package.name
    (package / "article.md").write_bytes(b"tampered\n")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        catalog_artifacts(package_root=package.parent)


def test_assisted_draft_receives_only_validated_ledger_and_is_isolated(tmp_path):
    package = _package(tmp_path)
    prompts = []

    def model(prompt):
        prompts.append(json.loads(prompt))
        return "A concise editorial transition for reviewer consideration."

    request = build_draft_request(package)
    draft = generate_assisted_draft(package, tmp_path / "drafts", model, model_id="fixture-model")
    assert prompts == [request]
    assert (draft / "draft.md").read_text(encoding="utf-8").startswith("A concise")
    metadata = json.loads((draft / "draft-manifest.json").read_text(encoding="utf-8"))
    assert metadata["source_of_truth"] == "deterministic-package"
    assert metadata["review_status"] == "pending"
    assert (package / "article.md").read_bytes() == b"# reviewed\n"


def test_assisted_draft_rejects_fact_like_output_and_tampered_ledger(tmp_path):
    package = _package(tmp_path)
    with pytest.raises(ValueError, match="factual or comparative"):
        generate_assisted_draft(package, tmp_path / "drafts", lambda _: "The result was 12% higher.", model_id="fixture")
    (package / "claim-ledger.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="claim ledger hash mismatch"):
        build_draft_request(package)


def _exportable_package(tmp_path, *, article_content=b"# reviewed\n"):
    package = _package(tmp_path / "packages")
    for name, content in {"article.html": b"<article>reviewed</article>\n",
                          "methodology-limitations.md": b"# Methodology\n",
                          "charts/result.svg": b"<svg aria-label=\"result\"></svg>\n"}.items():
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest_path = package / "package-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    (package / "article.md").write_bytes(article_content)
    manifest["artifacts"]["article.md"] = hashlib.sha256(article_content).hexdigest()
    manifest["artifacts"].update({name: hashlib.sha256(content).hexdigest()
                                   for name, content in {"article.html": b"<article>reviewed</article>\n",
                                                         "methodology-limitations.md": b"# Methodology\n",
                                                         "charts/result.svg": b"<svg aria-label=\"result\"></svg>\n"}.items()})
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    history = tmp_path / "history"
    approval = record_review(package, history, target_kind="package", decision="approved",
                             reviewer="Reviewer", reviewed_at="2026-09-16T12:00:00Z",
                             rationale="Approved for manual publication preparation.")
    return package, history, approval


def test_publication_export_is_approved_deterministic_and_excludes_drafts(tmp_path):
    package, history, approval = _exportable_package(tmp_path)
    package_before = {p.relative_to(package).as_posix(): p.read_bytes() for p in package.rglob("*") if p.is_file()}
    history_before = {p.relative_to(history).as_posix(): p.read_bytes() for p in history.rglob("*") if p.is_file()}
    exported = export_package(package, history, tmp_path / "exports")
    assert {p.relative_to(exported).as_posix() for p in exported.rglob("*") if p.is_file()} == {
        "article.md", "article.html", "methodology-limitations.md", "charts/result.svg", "export-manifest.json"}
    assert not list(exported.rglob("*draft*"))
    export_manifest = json.loads((exported / "export-manifest.json").read_text())
    assert export_manifest["approvals"][0]["review_id"] == approval.stem
    for name, expected in export_manifest["files"].items():
        assert hashlib.sha256((exported / name).read_bytes()).hexdigest() == expected
    replay = export_package(package, history, tmp_path / "exports")
    assert replay == exported
    assert package_before == {p.relative_to(package).as_posix(): p.read_bytes() for p in package.rglob("*") if p.is_file()}
    assert history_before == {p.relative_to(history).as_posix(): p.read_bytes() for p in history.rglob("*") if p.is_file()}


def test_publication_export_rejects_conflicts_rejections_and_tampering(tmp_path):
    package, history, _ = _exportable_package(tmp_path)
    exported = export_package(package, history, tmp_path / "exports")
    (exported / "article.md").write_bytes(b"conflict\n")
    with pytest.raises(FileExistsError, match="immutable export differs"):
        export_package(package, history, tmp_path / "exports")

    package, history, _ = _exportable_package(tmp_path / "rejected")
    record_review(package, history, target_kind="package", decision="rejected", reviewer="Reviewer",
                  reviewed_at="2026-09-16T12:01:00Z", rationale="Rejected for correction.")
    with pytest.raises(ValueError, match="latest effective review decision"):
        export_package(package, history, tmp_path / "rejected-exports")

    package, history, _ = _exportable_package(tmp_path / "tampered")
    review = next(history.rglob("*.json"))
    review.write_bytes(review.read_bytes().replace(b"Reviewer", b"Tampered"))
    with pytest.raises(ValueError):
        export_package(package, history, tmp_path / "tampered-exports")

    package, history, _ = _exportable_package(tmp_path / "secret", article_content=b"secret=fixture-secret\n")
    with pytest.raises(ValueError, match="secret"):
        export_package(package, history, tmp_path / "secret-exports")


def test_publication_export_cli_returns_json_and_nonzero_on_rejection(tmp_path):
    package, history, _ = _exportable_package(tmp_path)
    success = subprocess.run([sys.executable, "-m", "reporting.package", "export", "--package", str(package),
                              "--history-dir", str(history), "--output-root", str(tmp_path / "exports")],
                             capture_output=True, text=True)
    assert success.returncode == 0
    assert json.loads(success.stdout)["export_id"]
    failure = subprocess.run([sys.executable, "-m", "reporting.package", "export", "--package", str(package),
                              "--history-dir", str(tmp_path / "missing-history"), "--output-root", str(tmp_path / "no")],
                             capture_output=True, text=True)
    assert failure.returncode != 0
    assert json.loads(failure.stdout)["error"] == "export requires review history"


def test_publication_export_is_network_denied_and_path_safe(tmp_path, monkeypatch):
    package, history, _ = _exportable_package(tmp_path)
    import socket
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("publication export attempted network access")))
    export_package(package, history, tmp_path / "exports")

    package, history, _ = _exportable_package(tmp_path / "traversal")
    manifest_path = package / "package-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"]["../outside.md"] = hashlib.sha256(b"x").hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes package"):
        export_package(package, history, tmp_path / "exports2")
