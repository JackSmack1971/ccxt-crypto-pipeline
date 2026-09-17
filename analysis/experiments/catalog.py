"""Verified, read-only catalog and comparison boundary for experiment runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analysis.alpha import assert_feature_versions_compatible, assert_label_versions_compatible

from .runner import MANIFEST_VERSION
from .spec import experiment_spec_from_dict, experiment_spec_id

LEGACY_MANIFEST_VERSION = "phase6-run-v1"
LEGACY_ROBUST_MANIFEST_VERSION = "phase7-run-v1"
LEGACY_CURRENT_MANIFEST_VERSION = "phase7-run-v2"
LEGACY_CLOSURE_MANIFEST_VERSION = "phase7-run-v3"
LEGACY_PHASE8_MANIFEST_VERSION = "phase8r-run-v1"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    path: Path
    experiment_spec_id: str
    dataset_identity: str
    code_version: str
    experiment_name: str
    candidate_name: str
    candidate_horizon: str
    promotion_state: str
    research_question_id: str | None = None
    research_hypothesis_id: str | None = None


@dataclass(frozen=True)
class RunComparison:
    left_run_id: str
    right_run_id: str
    candidate_name: str
    horizon: str
    mean_return_delta: float | None
    sample_size_delta: int
    coverage_delta: float


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid experiment run artifact: {path}") from exc


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, default=str, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_run(run_dir: str | Path) -> RunRecord:
    """Verify an immutable run and return its catalog metadata without writing it."""
    path = Path(run_dir)
    manifest = _read_json(path / "manifest.json")
    manifest_version = manifest.get("manifest_version")
    if manifest_version not in {LEGACY_MANIFEST_VERSION, LEGACY_ROBUST_MANIFEST_VERSION,
                                LEGACY_CURRENT_MANIFEST_VERSION, LEGACY_CLOSURE_MANIFEST_VERSION,
                                LEGACY_PHASE8_MANIFEST_VERSION,
                                MANIFEST_VERSION} or manifest.get("immutable") is not True:
        raise ValueError(f"unsupported or mutable experiment run manifest: {path}")
    run_id = manifest.get("run_id")
    inputs = manifest.get("inputs")
    artifacts = manifest.get("artifacts")
    if not isinstance(run_id, str) or path.name != run_id or not isinstance(inputs, dict) or not isinstance(artifacts, dict):
        raise ValueError(f"invalid experiment run manifest structure: {path}")
    expected_run_id = hashlib.sha256(_canonical(inputs)).hexdigest()[:24]
    if run_id != expected_run_id:
        raise ValueError(f"experiment run identity mismatch: {path}")
    declared_manifest_version = inputs.get("manifest_version")
    if manifest_version in {LEGACY_PHASE8_MANIFEST_VERSION, MANIFEST_VERSION} \
            and declared_manifest_version != manifest_version:
        raise ValueError(f"experiment run manifest version is not identity-bound: {path}")
    if manifest_version not in {LEGACY_PHASE8_MANIFEST_VERSION, MANIFEST_VERSION} \
            and declared_manifest_version is not None:
        raise ValueError(f"experiment run manifest version is not identity-bound: {path}")
    for name, expected_hash in sorted(artifacts.items()):
        artifact_path = path / name
        try:
            content = artifact_path.read_bytes()
        except OSError as exc:
            raise ValueError(f"missing experiment run artifact: {artifact_path}") from exc
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise ValueError(f"experiment run artifact hash mismatch: {artifact_path}")

    required = {"spec.json", "candidate.json", "promotion.json", "definitions.json"}
    if manifest_version in {LEGACY_ROBUST_MANIFEST_VERSION, LEGACY_CURRENT_MANIFEST_VERSION,
                            LEGACY_CLOSURE_MANIFEST_VERSION, LEGACY_PHASE8_MANIFEST_VERSION,
                            MANIFEST_VERSION}:
        required.add("stability.json")
    if manifest_version in {LEGACY_CLOSURE_MANIFEST_VERSION, LEGACY_PHASE8_MANIFEST_VERSION,
                            MANIFEST_VERSION}:
        required.add("negative_controls.json")
    if manifest_version in {LEGACY_CLOSURE_MANIFEST_VERSION, LEGACY_PHASE8_MANIFEST_VERSION,
                            MANIFEST_VERSION}:
        required.add("validation_closure.json")
    if manifest_version in {LEGACY_PHASE8_MANIFEST_VERSION, MANIFEST_VERSION}:
        required.add("falsification.json")
    if not required <= set(artifacts):
        raise ValueError(f"experiment run manifest lacks required artifacts: {path}")
    spec = _read_json(path / "spec.json")
    # The legacy phase8r-run-v1 catalog format is produced by the same runner and
    # spec schema as the current manifest; it must keep the same provenance
    # verification strength rather than silently losing it when demoted.
    _verified_manifest_versions = {LEGACY_PHASE8_MANIFEST_VERSION, MANIFEST_VERSION}
    falsification = _read_json(path / "falsification.json") if manifest_version in _verified_manifest_versions else None
    if manifest_version in _verified_manifest_versions:
        parsed_spec = experiment_spec_from_dict(spec)
        if experiment_spec_id(parsed_spec) != inputs["experiment_spec_id"]:
            raise ValueError(f"experiment spec identity mismatch: {path}")
        if (parsed_spec.research_question_id != inputs.get("research_question_id") or
                parsed_spec.research_hypothesis_id != inputs.get("research_hypothesis_id")):
            raise ValueError(f"experiment research binding mismatch: {path}")
        expected_falsification_policy = {"version": parsed_spec.falsification.version,
                                         "methods": list(parsed_spec.falsification.methods),
                                         "inapplicable_methods": list(parsed_spec.falsification.inapplicable_methods)}
        if falsification.get("policy") != expected_falsification_policy:
            raise ValueError(f"experiment falsification policy mismatch: {path}")
    candidate = _read_json(path / "candidate.json")
    promotion = _read_json(path / "promotion.json")
    return RunRecord(run_id, path, inputs["experiment_spec_id"], inputs["dataset_identity"],
                     inputs["code_version"], spec["name"], candidate["name"], candidate["horizon"],
                     promotion["state"], inputs.get("research_question_id"),
                     inputs.get("research_hypothesis_id"))


def catalog_runs(root: str | Path) -> tuple[RunRecord, ...]:
    """Index immediate child run directories deterministically; invalid runs fail closed."""
    path = Path(root)
    if not path.exists():
        return ()
    return tuple(load_run(child) for child in sorted(path.iterdir(), key=lambda item: item.name)
                 if child.is_dir())


def _methodology(spec: dict[str, Any]) -> dict[str, Any]:
    value = dict(spec)
    value.pop("name", None)
    value.pop("feature_policy_version", None)
    labels = []
    for label in value.get("labels", []):
        normalized = dict(label)
        normalized.pop("version", None)
        labels.append(normalized)
    value["labels"] = labels
    return value


def compare_runs(left_dir: str | Path, right_dir: str | Path) -> RunComparison:
    """Compare candidate summaries only after proving methodology compatibility."""
    left, right = load_run(left_dir), load_run(right_dir)
    left_spec, right_spec = _read_json(left.path / "spec.json"), _read_json(right.path / "spec.json")
    left_defs, right_defs = _read_json(left.path / "definitions.json"), _read_json(right.path / "definitions.json")

    if set(left_defs["features"]) != set(right_defs["features"]):
        raise ValueError("incompatible experiment feature sets")
    for name in sorted(left_defs["features"]):
        assert_feature_versions_compatible(name, left_defs["features"][name]["version"],
                                           right_defs["features"][name]["version"])
    if set(left_defs["labels"]) != set(right_defs["labels"]):
        raise ValueError("incompatible experiment label horizons")
    for horizon in sorted(left_defs["labels"]):
        assert_label_versions_compatible(horizon, left_defs["labels"][horizon]["version"],
                                         right_defs["labels"][horizon]["version"])
    if _methodology(left_spec) != _methodology(right_spec):
        raise ValueError("incompatible experiment methodology")

    a, b = _read_json(left.path / "candidate.json"), _read_json(right.path / "candidate.json")
    mean_delta = None if a["mean_return"] is None or b["mean_return"] is None else b["mean_return"] - a["mean_return"]
    return RunComparison(left.run_id, right.run_id, a["name"], a["horizon"], mean_delta,
                         b["sample_size"] - a["sample_size"], b["coverage"] - a["coverage"])
