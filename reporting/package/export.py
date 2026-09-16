"""Offline, immutable export bundles for manually publishing reviewed packages."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .catalog import verify_package
from .generate import _security_scan
from .review_history import load_review, review_history


VERSION = "phase8-export-v1"
_PUBLICATION_FILES = {"article.md", "article.html", "methodology-limitations.md"}


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _safe_relative(name: str) -> Path:
    relative = Path(name)
    if not isinstance(name, str) or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"export path is unsafe: {name}")
    return relative


def _effective_approvals(history_dir: Path, package: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = review_history(history_dir, package.name)
    if not records:
        raise ValueError("export requires review history")
    manifest_hash = hashlib.sha256((package / "package-manifest.json").read_bytes()).hexdigest()
    for record in records:
        target = record.get("target")
        if target != {"kind": "package", "id": package.name, "manifest_sha256": manifest_hash}:
            raise ValueError("review decision is not bound to this package")

    by_id = {record["review_id"]: record for record in records}
    superseded: set[str] = set()
    for record in records:
        prior_id = record.get("supersedes_review_id")
        if record["decision"] == "superseded" and not prior_id:
            raise ValueError("superseded review lacks its predecessor")
        if prior_id:
            if prior_id not in by_id or prior_id == record["review_id"]:
                raise ValueError("review supersession is ambiguous")
            superseded.add(prior_id)

    active = [record for record in records if record["review_id"] not in superseded]
    decisions = [record for record in active if record["decision"] in {"approved", "rejected"}]
    if not decisions:
        raise ValueError("export requires an approved review decision")
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for record in decisions:
        timestamp = datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
        parsed.append((timestamp, record))
    parsed.sort(key=lambda item: item[0])
    if len(parsed) > 1 and any(parsed[index][0] == parsed[index - 1][0] for index in range(1, len(parsed))):
        raise ValueError("review decisions have an ambiguous effective timestamp")
    if parsed[-1][1]["decision"] != "approved":
        raise ValueError("latest effective review decision is not approved")
    approvals = [record for record in active if record["decision"] == "approved"]
    if not approvals:
        raise ValueError("export requires an approved review decision")
    return [{key: record[key] for key in ("review_id", "reviewer", "reviewed_at", "rationale", "notes")}
            for record in approvals]


def _publication_files(package: Path, artifacts: dict[str, str]) -> dict[str, bytes]:
    names = sorted(name for name in artifacts if name in _PUBLICATION_FILES or name.startswith("charts/"))
    if not {"article.md", "article.html"}.issubset(names):
        raise ValueError("package lacks deterministic publication artifacts")
    files: dict[str, bytes] = {}
    for name in names:
        relative = _safe_relative(name)
        if name.startswith("charts/") and (len(relative.parts) != 2 or relative.suffix != ".svg"):
            raise ValueError(f"unsafe publication artifact: {name}")
        source = (package / relative).resolve()
        if package not in source.parents or not source.is_file():
            raise ValueError(f"missing publication artifact: {name}")
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != artifacts[name]:
            raise ValueError(f"source artifact hash mismatch: {name}")
        _security_scan(content.decode("utf-8", errors="replace"))
        files[name] = content
    return files


def export_package(package_dir: str | Path, history_dir: str | Path, output_root: str | Path) -> Path:
    """Create a deterministic, content-addressed bundle for manual publication."""
    package = Path(package_dir).resolve()
    manifest, artifacts = verify_package(package)
    approvals = _effective_approvals(Path(history_dir).resolve(), package, manifest)
    files = _publication_files(package, artifacts)
    renderer_versions = manifest.get("renderer_version", {})
    if not isinstance(renderer_versions, dict):
        raise ValueError("package renderer versions are malformed")
    identity = {"version": VERSION, "package_id": package.name, "source_artifacts": artifacts,
                "approvals": approvals, "renderer_versions": renderer_versions, "files": sorted(files)}
    export_id = hashlib.sha256(_json(identity)).hexdigest()[:24]
    export_manifest = {"export_version": VERSION, "export_id": export_id,
                       "source_package_id": package.name,
                       "source_package_manifest_sha256": hashlib.sha256((package / "package-manifest.json").read_bytes()).hexdigest(),
                       "source_artifacts": artifacts, "approvals": approvals,
                       "renderer_versions": renderer_versions, "publication": "manual-preparation",
                       "files": {name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())}}
    _security_scan(export_manifest)
    contents = {**files, "export-manifest.json": _json(export_manifest)}
    root = Path(output_root).resolve()
    target = root / export_id
    if target.exists():
        existing = {path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        if existing != contents:
            raise FileExistsError(f"immutable export differs: {target}")
        return target
    temp = root / f".{export_id}.tmp"
    if temp.exists():
        raise FileExistsError(f"incomplete export exists: {temp}")
    try:
        for name, content in sorted(contents.items()):
            path = temp / _safe_relative(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise
    return target
