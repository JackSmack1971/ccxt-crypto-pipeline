from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping


VERSION = "phase4-approved-v1"
_ROOT_FIELDS = {
    "handoff_version", "handoff_id", "approved", "immutable", "approval",
    "research_run", "research_artifacts", "staged_tables", "title",
    "dataset_identity", "query_config_identity", "config_identity",
    "code_version", "time_range", "claims", "charts", "methodology",
}
_APPROVAL_FIELDS = {"status", "identity", "reviewer", "approved_at", "scope"}


def _dump(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_fields(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")


def validate_approved_handoff(manifest: Mapping[str, Any]) -> None:
    """Validate the structural approval contract before Phase 4 reads inputs."""
    _strict_fields(manifest, _ROOT_FIELDS, "approved handoff")
    if manifest.get("handoff_version") != VERSION or manifest.get("immutable") is not True:
        raise ValueError("unsupported or mutable approved handoff")
    approval = manifest.get("approval")
    if not isinstance(approval, dict):
        raise ValueError("approved handoff lacks approval metadata")
    _strict_fields(approval, _APPROVAL_FIELDS, "approval")
    required = ("identity", "reviewer", "approved_at", "scope")
    if approval.get("status") != "approved" or any(not approval.get(item) for item in required):
        raise ValueError("approved handoff requires complete approval metadata")
    research = manifest.get("research_run")
    if not isinstance(research, dict) or not research.get("run_id") or not research.get("path") or not research.get("sha256"):
        raise ValueError("approved handoff lacks research-run identity")
    if not isinstance(manifest.get("research_artifacts"), dict) or not manifest["research_artifacts"]:
        raise ValueError("approved handoff lacks staged research artifacts")


def build_approved_handoff(
    research_run_dir: str | Path,
    output_dir: str | Path,
    *,
    approval: Mapping[str, Any],
    staged_artifacts: Mapping[str, str],
    presentation: Mapping[str, Any] | None = None,
) -> Path:
    """Create a deterministic, immutable Phase 3-to-Phase 4 handoff.

    The Phase 3 directory is read-only; staged bytes are copied into the handoff.
    ``presentation`` contains only Phase 4 presentation declarations (claims,
    charts, and methodology), never replacement research semantics.
    """
    source = Path(research_run_dir).resolve()
    research_path = source / "manifest.json"
    research = json.loads(research_path.read_text(encoding="utf-8"))
    if research.get("manifest_version") != "phase3-v1" or research.get("immutable") is not True:
        raise ValueError("research run is not an immutable Phase 3 artifact")
    if not research.get("run_id") or not isinstance(research.get("artifacts"), dict):
        raise ValueError("research run lacks identity or artifact hashes")
    _strict_fields(dict(approval), _APPROVAL_FIELDS, "approval")
    if approval.get("status") != "approved":
        raise ValueError("handoff approval status must be approved")
    presentation = dict(presentation or {})
    allowed_presentation = {"title", "dataset_identity", "query_config_identity", "config_identity",
                            "code_version", "time_range", "claims", "charts", "methodology"}
    _strict_fields(presentation, allowed_presentation, "presentation")
    dataset = presentation.get("dataset_identity", research.get("inputs", {}).get("dataset_identity"))
    if not dataset:
        raise ValueError("handoff requires dataset identity")

    target_data = {"research_run_id": research["run_id"], "research_manifest_sha256": _sha256(research_path),
                   "approval": dict(approval),
                   "staged_artifacts": {k: v for k, v in sorted(staged_artifacts.items())},
                   "presentation": presentation}
    handoff_id = hashlib.sha256(_dump(target_data)).hexdigest()[:24]
    target = Path(output_dir).resolve() / handoff_id
    target.mkdir(parents=True, exist_ok=True)
    linked_manifest = target / "research-manifest.json"
    research_bytes = research_path.read_bytes()
    if linked_manifest.exists() and linked_manifest.read_bytes() != research_bytes:
        raise FileExistsError(f"immutable handoff artifact differs: {linked_manifest}")
    if not linked_manifest.exists():
        linked_manifest.write_bytes(research_bytes)
    linked = {"path": linked_manifest.name, "sha256": _sha256(linked_manifest), "run_id": research["run_id"]}
    research_artifacts = {}
    staged_tables = {}
    for alias, artifact_name in sorted(staged_artifacts.items()):
        if artifact_name not in research["artifacts"]:
            raise ValueError(f"staged artifact is not declared by Phase 3: {artifact_name}")
        source_artifact = source / artifact_name
        if not source_artifact.is_file() or _sha256(source_artifact) != research["artifacts"][artifact_name]:
            raise ValueError(f"Phase 3 artifact is missing or changed: {artifact_name}")
        destination = target / artifact_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != source_artifact.read_bytes():
            raise FileExistsError(f"immutable handoff artifact differs: {destination}")
        if not destination.exists():
            shutil.copyfile(source_artifact, destination)
        entry = {"path": artifact_name, "sha256": _sha256(destination)}
        research_artifacts[artifact_name] = entry
        staged_tables[alias] = entry
    manifest = {"handoff_version": VERSION, "handoff_id": handoff_id, "approved": True, "immutable": True,
                "approval": dict(approval), "research_run": linked, "research_artifacts": research_artifacts,
                "staged_tables": staged_tables, **presentation, "dataset_identity": dataset}
    validate_approved_handoff(manifest)
    manifest_path = target / "manifest.json"
    content = _dump(manifest)
    if manifest_path.exists() and manifest_path.read_bytes() != content:
        raise FileExistsError(f"immutable handoff manifest differs: {manifest_path}")
    if not manifest_path.exists():
        manifest_path.write_bytes(content)
    return target
