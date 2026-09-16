import json
import hashlib
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from reporting.package import build_approved_handoff, generate_package
from reporting.package.handoff import _dump
from reporting.claims.model import (Claim, Derivation, Evidence, _COMPARE, _DURATION,
                                    _NUMBER_WORD, _derived_value, validate_claims)
from reporting.render.static import render_svg, validate_accessibility
from analysis.alpha import (CohortConfig, FeatureDefinition, FeatureRegistry, LabelDefinition,
                            PromotionEvidence, build_split, compute_features,
                            evaluate_candidate_promotion, extract_cohort, generate_labels,
                            score_candidate, write_research_run)
from analysis.datasets import DatasetPolicy, DatasetSnapshot
from storage.db import connect, insert_event, insert_ohlcv_batch, upsert_asset


def _claim_for_derivation(operation, values):
    return Claim(
        id="derived",
        text="derived value",
        evidence=tuple(Evidence("results", index, "dataset", "config", {"start": "a", "end": "b"}, "fixture")
                       for index in range(len(values))),
        derivation=Derivation(source_field="value", operation=operation,
                              unit="unitless", source_unit="unitless"),
    )


def test_compare_regex_rejects_word_boundary_near_misses():
    assert _COMPARE.search("outperformer") is None
    assert _COMPARE.search("outperformed").group(0) == "outperformed"


def test_duration_regex_distinguishes_hyphenated_singular_and_near_misses():
    assert _DURATION.search("ten-hour").group(0) == "ten-hour"
    assert _DURATION.search("tenhour").group(0) == "tenhour"
    assert _DURATION.search("ten hours") is None


def test_number_word_regex_requires_boundaries_before_adjacent_words():
    assert _NUMBER_WORD.search("oneworld") is None
    assert _NUMBER_WORD.search("one world").group(0) == "one"


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
    assert '<meta name="review-status" content="pending">' in (first / "article.html").read_text()
    assert '<svg ' in (first / "article.html").read_text()


@pytest.mark.parametrize(("operation", "values", "expected"), [
    ("identity", (3.0,), 3.0),
    ("mean", (2.0, 4.0), 3.0),
    ("difference", (7.0, 2.0), 5.0),
    ("ratio", (6.0, 2.0), 3.0),
    ("percent_change", (12.0, 8.0), 50.0),
])
def test_phase4_claim_derivations_compute_each_supported_operation(operation, values, expected):
    claim = _claim_for_derivation(operation, values)
    assert _derived_value(claim, {"results": [{"value": value} for value in values]}) == pytest.approx(expected)


@pytest.mark.parametrize(("operation", "values", "message"), [
    ("unsupported", (1.0,), "unsupported derivation operation"),
    ("identity", (True,), "source is not numeric"),
    ("identity", (float("inf"),), "source is non-finite"),
    ("identity", (1.0, 2.0), "identity derivation requires one"),
    ("difference", (1.0,), "difference derivation requires two"),
    ("ratio", (1.0, 0.0), "ratio has a zero denominator"),
    ("percent_change", (1.0, 0.0), "percent_change has a zero denominator"),
])
def test_phase4_claim_derivations_reject_invalid_inputs(operation, values, message):
    with pytest.raises(ValueError, match=message):
        _derived_value(_claim_for_derivation(operation, values),
                       {"results": [{"value": value} for value in values]})


def _claim_manifest_and_rows(*, text, operation, values, sides=("left", "right")):
    evidence = tuple(Evidence("results", index, "fixture-dataset", "fixture-config",
                              {"start": "2025-01-01", "end": "2025-01-02"}, "fixture", side)
                     for index, side in enumerate(sides[:len(values)]))
    claim = Claim("comparison", text + " ratio", evidence=evidence,
                  derivation=Derivation("value", operation, "ratio", "ratio", 1,
                                        sides[0], sides[1]))
    manifest = {"dataset_identity": "fixture-dataset", "query_config_identity": "fixture-config",
                "time_range": {"start": "2025-01-01", "end": "2025-01-02"}}
    return claim, manifest, {"results": [{"value": value} for value in values]}


def test_phase4_claim_ledger_accepts_and_checks_comparative_provenance():
    claim, manifest, staged = _claim_manifest_and_rows(
        text="left was twice right: left versus right.", operation="ratio", values=(4.0, 2.0))
    validated = validate_claims((claim,), manifest, staged)
    assert validated[0]["evidence"][0]["side"] == "left"
    assert validated[0]["derivation"]["right_label"] == "right"

    mismatched, _, _ = _claim_manifest_and_rows(
        text="left was twice right: left versus right.", operation="ratio", values=(4.0, 2.0),
        sides=("other", "right"))
    mismatched = replace(mismatched, derivation=replace(mismatched.derivation, left_label="left"))
    with pytest.raises(ValueError, match="comparative evidence sides"):
        validate_claims((mismatched,), manifest, staged)


@pytest.mark.parametrize(("text", "values", "message"), [
    ("left was twice right: left versus right.", (3.0, 2.0), "twice comparison disagrees"),
    ("left was higher than right: left versus right.", (1.0, 2.0), "direction disagrees"),
    ("left was lower than right: left versus right.", (2.0, 1.0), "direction disagrees"),
])
def test_phase4_claim_ledger_rejects_comparative_semantic_mismatches(text, values, message):
    claim, manifest, staged = _claim_manifest_and_rows(text=text, operation="ratio", values=values)
    with pytest.raises(ValueError, match=message):
        validate_claims((claim,), manifest, staged)


_CLAIM_TIME_RANGE = {"start": "2025-01-01", "end": "2025-01-02"}
_CLAIM_MANIFEST = {"dataset_identity": "fixture-dataset", "query_config_identity": "fixture-config",
                   "time_range": _CLAIM_TIME_RANGE}
_MISSING_ROW_CLAIM = Claim(
    "missing", "A fact.",
    evidence=(Evidence("results", 1, "fixture-dataset", "fixture-config", _CLAIM_TIME_RANGE, "fixture"),),
)


@pytest.mark.parametrize("claims, staged, message", [
    pytest.param((Claim("duplicate", "A fact.", kind="interpretation"),
                  Claim("duplicate", "Another fact.", kind="interpretation")), {}, "duplicate claim"),
    pytest.param((_MISSING_ROW_CLAIM,), {"results": [{"value": 1.0}]}, "missing row"),
])
def test_phase4_claim_ledger_rejects_duplicate_ids_and_missing_rows(claims, staged, message):
    with pytest.raises(ValueError, match=message):
        validate_claims(claims, _CLAIM_MANIFEST, staged)


def test_phase4_static_renderer_sorts_declared_x_values_before_plotting():
    spec = {"id": "returns", "x_column": "time", "y_column": "return", "x_unit": "hours",
            "y_unit": "percent", "missing_behavior": "explicit_state", "source_attribution": "fixture",
            "alt_text": "Observed return percent over time.", "transformations": ["sort_x"],
            "width": 800, "height": 450}
    svg = render_svg(spec, [{"time": 2, "return": 20}, {"time": 1, "return": 10}])
    assert 'points="60.000,400.000 760.000,50.000"' in svg


def test_phase4_static_renderer_preserves_missing_state_and_fail_policy():
    spec = {"id": "returns", "x_column": "time", "y_column": "return", "x_unit": "hours",
            "y_unit": "percent", "missing_behavior": "explicit_state", "source_attribution": "fixture",
            "alt_text": "Observed return percent over time.", "width": 800, "height": 450}
    svg = render_svg(spec, [{"time": 1, "return": 10}, {"time": 2, "return": None}])
    assert 'data-missing="true"' in svg
    assert "Unavailable observations omitted" in svg

    spec["missing_behavior"] = "fail"
    with pytest.raises(ValueError, match="contains missing values"):
        render_svg(spec, [{"time": 1, "return": None}])


def _renderer_spec(**overrides):
    spec = {"id": "returns", "x_column": "time", "y_column": "return", "x_unit": "hours",
            "y_unit": "percent", "missing_behavior": "explicit_state", "source_attribution": "fixture",
            "alt_text": "Observed return percent over time.", "width": 800, "height": 450}
    spec.update(overrides)
    return spec


@pytest.mark.parametrize(("rows", "overrides", "message"), [
    ([{"time": "one", "return": 1}], {"missing_behavior": "fail"}, "contains unsupported values"),
    ([{"time": 1, "return": float("inf")}], {}, "contains non-finite values"),
    ([{"time": 1, "return": None}], {"missing_behavior": "fail"}, "contains missing values"),
    ([{"time": 1, "return": None}], {"annotations": [{"type": "horizontal_line", "value": 1, "label": "x", "source": "fixture"}]},
     "cannot apply annotations"),
    ([{"time": 1, "return": 1}], {"width": 319}, "has invalid dimensions"),
    ([{"time": 1, "return": 1}], {"height": True}, "has invalid dimensions"),
])
def test_phase4_renderer_rejects_unsupported_values_and_invalid_layout(rows, overrides, message):
    with pytest.raises(ValueError, match=message):
        render_svg(_renderer_spec(**overrides), rows)


def test_phase4_renderer_accessibility_validator_rejects_malformed_or_incomplete_svg():
    spec = _renderer_spec()
    svg = render_svg(spec, [{"time": 1, "return": 1}])
    validate_accessibility(svg, spec)

    for malformed in (
        svg.replace('role="img"', 'role="figure"'),
        svg.replace("<title>returns</title>", "<title></title>"),
        svg.replace('data-missing="false"', 'data-missing="maybe"'),
        svg.replace('points="60.000,400.000"', 'points="not-a-point"'),
    ):
        with pytest.raises(ValueError, match="accessibility validation"):
            validate_accessibility(malformed, spec)

    with pytest.raises(ValueError, match="structure validation"):
        validate_accessibility("<not-svg>", spec)


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


def test_phase8_html_preserves_accessible_missing_state_and_is_deterministic(tmp_path):
    input_dir = approved_input(tmp_path, missing=True)
    first = generate_package(input_dir, tmp_path / "out")
    html = (first / "article.html").read_text()
    assert '<html lang="en">' in html
    assert "pending human review" in html
    assert "No supported observations" in html
    assert "<h2 id=\"methodology-heading\">Methodology and limitations</h2>" in html
    second = generate_package(input_dir, tmp_path / "out")
    assert (first / "article.html").read_bytes() == (second / "article.html").read_bytes()


def test_phase8_html_escapes_claim_text(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["title"] = "<unsafe title>"
    manifest["claims"][0]["text"] = "Observed <value> was 1.5%."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    package = generate_package(input_dir, tmp_path / "out")
    html = (package / "article.html").read_text()
    assert "&lt;unsafe title&gt;" in html and "&lt;value&gt;" in html
    assert "<unsafe title>" not in html and "<value>" not in html


def test_phase4_rejects_changed_staged_content(tmp_path):
    input_dir = approved_input(tmp_path)
    (input_dir / "results.json").write_text(json.dumps([{"time": 1, "return": 9.0}]), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_claim_with_mismatched_dataset_identity(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["evidence"][0]["dataset_identity"] = "other-dataset"
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="mismatched dataset identity"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_claim_when_rendered_number_disagrees_with_evidence(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 9.9%."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="rendered value disagrees"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_requires_derivation_for_numeric_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0].pop("derivation")
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="lacks a derivation"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_unknown_claim_fields(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["unexpected"] = "not allowed"
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unknown fields"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_attached_number_unit_mismatch(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 999.9USD."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="rendered value disagrees"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_requires_evidence_for_factual_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0] = {"id": "fact", "text": "The cohort was sealed.", "kind": "fact"}
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="factual claim has no evidence"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_unsupported_chart_transformation(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["charts"][0]["transformations"] = ["interpolate"]
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported transformation"):
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
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="not approved"):
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
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="comparative derivation requires two evidence rows"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_claim_with_wrong_unit_text(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 1.5 dollars."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="invalid formatting policy"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_reversed_comparative_claim(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The observed return was 1.5% lower."
    manifest["claims"][0]["derivation"] = {"source_field": "return", "operation": "identity", "unit": "percent", "source_unit": "percent", "decimals": 1}
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="comparative derivation requires two evidence rows"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_untyped_exceeded_comparison(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "A exceeded B by 1.0%."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="comparative derivation requires two evidence rows"):
        generate_package(input_dir, tmp_path / "out")


def test_phase4_rejects_word_number_mismatch_after_duration_phrase(tmp_path):
    input_dir = approved_input(tmp_path)
    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["claims"][0]["text"] = "The one-hour return was five percent."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="duration is not supported"):
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
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported annotation"):
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
                     "source_attribution": "approved Phase 3 result", "alt_text": "Observed log-return label."}],
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
        "claims": [{"id": "label", "text": f"The observed log-return was {labels[0].value:.6f}.", "evidence": [{
            "artifact": "labels", "row": 0, "dataset_identity": dataset.dataset_identity,
            "query_config_identity": "fixture-phase4-config", "time_range": time_range,
            "uncertainty": "fixture"}], "derivation": {"source_field": "value", "operation": "identity", "unit": "log-return", "source_unit": "log-return", "decimals": 6}}],
        "charts": [{"id": "label", "data_artifact": "labels", "x_column": "value", "y_column": "value",
                     "x_unit": "log-return", "y_unit": "log-return", "missing_behavior": "explicit_state",
                     "source_attribution": "approved Phase 3 result", "alt_text": "Observed one-hour log-return."}],
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
    with pytest.raises(ValueError, match="approved handoff"):
        generate_package(input_dir, tmp_path / "out")

    manifest = json.loads((input_dir / "manifest.json").read_text())
    manifest["approved"] = True
    manifest["claims"][0]["text"] = "The authorization: Bearer fixture-token must not be emitted."
    rekey_handoff(manifest)
    (input_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="secret or secret-bearing URL"):
        generate_package(input_dir, tmp_path / "out")
