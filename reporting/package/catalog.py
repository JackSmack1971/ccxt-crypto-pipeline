"""Read-only catalog and search boundary for immutable research artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .review_history import review_history


@dataclass(frozen=True)
class ArtifactRecord:
    """Verified metadata for one immutable research run or report package."""

    kind: str
    artifact_id: str
    path: str
    metadata: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid catalog artifact: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"catalog manifest must be an object: {path}")
    return value


def _reviews(history_dir: str | Path | None, artifact_id: str) -> dict[str, Any]:
    if history_dir is None:
        return {"review_count": 0, "latest_decision": None}
    records = review_history(history_dir, artifact_id)
    return {"review_count": len(records),
            "latest_decision": records[-1]["decision"] if records else None}


def _research_record(path: Path, history_dir: str | Path | None) -> ArtifactRecord:
    from analysis.experiments.catalog import load_run

    run = load_run(path)
    spec = _read_json(path / "spec.json")
    metadata = {"experiment_name": run.experiment_name,
                "candidate_name": run.candidate_name,
                "candidate_horizon": run.candidate_horizon,
                "promotion_state": run.promotion_state,
                "experiment_spec_id": run.experiment_spec_id,
                "dataset_identity": run.dataset_identity,
                "code_version": run.code_version,
                **_reviews(history_dir, run.run_id)}
    return ArtifactRecord("research_run", run.run_id, str(path.resolve()), metadata)


def _package_record(path: Path, history_dir: str | Path | None) -> ArtifactRecord:
    manifest_path = path / "package-manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("immutable") is not True or manifest.get("package_id") != path.name:
        raise ValueError(f"unsupported or mutable report package: {path}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError(f"report package lacks artifact hashes: {path}")
    for name, expected in sorted(artifacts.items()):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"report package artifact escapes package: {name}")
        artifact = (path / relative).resolve()
        if path.resolve() not in artifact.parents or not artifact.is_file():
            raise ValueError(f"missing report package artifact: {name}")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
            raise ValueError(f"report package artifact hash mismatch: {name}")
    inputs = manifest.get("inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError(f"report package inputs are malformed: {path}")
    metadata = {"package_version": manifest.get("package_version"),
                "review_status": manifest.get("review_status"),
                "research_run_id": inputs.get("research_run_id"),
                "dataset_identity": inputs.get("dataset_identity"),
                "output_formats": manifest.get("output_formats", []),
                "renderer_version": manifest.get("renderer_version", {}),
                **_reviews(history_dir, path.name)}
    return ArtifactRecord("package", path.name, str(path.resolve()), metadata)


def _records(root: str | Path | None, kind: str, loader, history_dir: str | Path | None) -> list[ArtifactRecord]:
    if root is None:
        return []
    path = Path(root)
    if not path.exists():
        return []
    if not path.is_dir():
        raise ValueError(f"catalog root is not a directory: {path}")
    return [loader(child, history_dir) for child in sorted(path.iterdir(), key=lambda item: item.name)
            if child.is_dir()]


def catalog_artifacts(*, research_root: str | Path | None = None,
                      package_root: str | Path | None = None,
                      history_dir: str | Path | None = None,
                      query: str | None = None) -> tuple[ArtifactRecord, ...]:
    """Verify, index, and optionally search immediate immutable artifacts.

    This function never writes to the artifact or review-history roots.
    """
    if research_root is None and package_root is None:
        raise ValueError("at least one catalog root is required")
    records = _records(research_root, "research_run", _research_record, history_dir)
    records += _records(package_root, "package", _package_record, history_dir)
    records.sort(key=lambda item: (item.kind, item.artifact_id))
    if query is None or not query.strip():
        return tuple(records)
    needle = query.casefold().strip()
    return tuple(item for item in records
                 if needle in json.dumps(asdict(item), sort_keys=True, default=str).casefold())
