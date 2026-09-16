"""Immutable review history for verified research and report artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REVIEW_VERSION = "phase8-review-v1"
_DECISIONS = {"approved", "rejected", "superseded", "note"}
_FIELDS = {"review_version", "review_id", "target", "decision", "reviewer", "reviewed_at",
           "rationale", "notes", "supersedes_review_id"}


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("review requires an ISO-8601 reviewed_at timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("review reviewed_at timestamp must include a timezone")
    return value


def _verified_target(target: str | Path, target_kind: str) -> dict[str, str]:
    path = Path(target)
    if target_kind == "research_run":
        from analysis.experiments.catalog import load_run
        record = load_run(path)
        manifest = path / "manifest.json"
        target_id = record.run_id
    elif target_kind == "package":
        manifest = path / "package-manifest.json"
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid report package: {path}") from exc
        if value.get("immutable") is not True or value.get("package_id") != path.name:
            raise ValueError(f"unsupported or mutable report package: {path}")
        artifacts = value.get("artifacts")
        if not isinstance(artifacts, dict):
            raise ValueError(f"report package lacks artifact hashes: {path}")
        for name, expected in sorted(artifacts.items()):
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"report package artifact escapes package: {name}")
            artifact = path / name
            if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
                raise ValueError(f"report package artifact hash mismatch: {name}")
        target_id = value["package_id"]
    else:
        raise ValueError("review target kind must be research_run or package")
    return {"kind": target_kind, "id": target_id,
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}


def record_review(target: str | Path, history_dir: str | Path, *, target_kind: str,
                  decision: str, reviewer: str, reviewed_at: str, rationale: str = "",
                  notes: str = "", supersedes_review_id: str | None = None) -> Path:
    """Record an immutable review decision bound to the target's current manifest."""
    if decision not in _DECISIONS:
        raise ValueError(f"unsupported review decision: {decision}")
    if not reviewer.strip() or (decision != "note" and not rationale.strip()):
        raise ValueError("review requires a reviewer and rationale")
    if decision == "note" and not notes.strip() and not rationale.strip():
        raise ValueError("review note requires notes or rationale")
    _timestamp(reviewed_at)
    verified = _verified_target(target, target_kind)
    if decision == "superseded" and not supersedes_review_id:
        raise ValueError("superseded review requires supersedes_review_id")
    if supersedes_review_id:
        prior = load_review(Path(history_dir) / verified["id"] / f"{supersedes_review_id}.json")
        if prior["target"] != verified:
            raise ValueError("superseded review targets a different artifact")
    payload = {"review_version": REVIEW_VERSION, "target": verified, "decision": decision,
               "reviewer": reviewer.strip(), "reviewed_at": reviewed_at,
               "rationale": rationale.strip(), "notes": notes.strip(),
               "supersedes_review_id": supersedes_review_id}
    review_id = hashlib.sha256(_canonical(payload)).hexdigest()[:24]
    content = _canonical({"review_id": review_id, **payload})
    path = Path(history_dir) / verified["id"] / f"{review_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != content:
        raise FileExistsError(f"immutable review differs: {path}")
    if not path.exists():
        path.write_bytes(content)
    return path


def load_review(path: str | Path) -> dict[str, Any]:
    """Load and verify one immutable review record."""
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid review record: {path}") from exc
    if set(value) != _FIELDS or value.get("review_version") != REVIEW_VERSION:
        raise ValueError(f"unsupported review record: {path}")
    if value.get("review_id") != path.stem or value.get("decision") not in _DECISIONS:
        raise ValueError(f"invalid review record identity: {path}")
    payload = {key: value[key] for key in _FIELDS if key != "review_id"}
    expected = hashlib.sha256(_canonical(payload)).hexdigest()[:24]
    if expected != value["review_id"]:
        raise ValueError(f"review record identity mismatch: {path}")
    _timestamp(value["reviewed_at"])
    target = value["target"]
    if not isinstance(target, dict) or set(target) != {"kind", "id", "manifest_sha256"}:
        raise ValueError(f"invalid review target: {path}")
    return value


def review_history(history_dir: str | Path, target_id: str) -> tuple[dict[str, Any], ...]:
    """Return verified records for one target in deterministic order."""
    relative = Path(target_id)
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ValueError("review target id must be a safe directory name")
    root = Path(history_dir) / target_id
    if not root.exists():
        return ()
    return tuple(load_review(path) for path in sorted(root.glob("*.json"), key=lambda item: item.name))
