import hashlib
import json
import subprocess
import sys

import pytest

from reporting.package.catalog import catalog_artifacts
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
