"""Narrow local control API over the existing experiment engine."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from analysis.datasets import DatasetSnapshot

from .catalog import RunRecord, load_run
from .runner import run_experiment
from .spec import ExperimentSpec, experiment_spec_from_dict, experiment_spec_id

APPROVAL_VERSION = "phase6-run-approval-v1"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_experiment_spec(path: str | Path) -> ExperimentSpec:
    """Load JSON and validate it through the canonical ``ExperimentSpec``."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid experiment spec file: {path}") from exc
    return experiment_spec_from_dict(value)


def validate_experiment_spec(path: str | Path) -> str:
    """Validate a spec file and return its deterministic identity."""
    return experiment_spec_id(load_experiment_spec(path))


def execute_experiment(spec: str | Path | ExperimentSpec, snapshot: DatasetSnapshot,
                       output_dir: str | Path) -> Path:
    """Execute via the sole runner; this boundary contains no research logic."""
    resolved = load_experiment_spec(spec) if isinstance(spec, (str, Path)) else spec
    return run_experiment(resolved, snapshot, output_dir)


def inspect_experiment_run(run_dir: str | Path) -> RunRecord:
    """Hash-verify and inspect an immutable run through the catalog boundary."""
    return load_run(run_dir)


def approve_experiment_run(run_dir: str | Path, approval_dir: str | Path, *, reviewer: str,
                           reviewed_at: str, rationale: str) -> Path:
    """Write a separate immutable human attestation bound to a verified run.

    Approval records never alter the run, its promotion state, or its sealed
    holdout. They attest only that the named reviewer approved the inspected
    immutable artifact.
    """
    if not reviewer.strip() or not rationale.strip():
        raise ValueError("approval requires a reviewer and rationale")
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("approval requires an ISO-8601 reviewed_at timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("approval reviewed_at timestamp must include a timezone")
    record = load_run(run_dir)
    manifest_hash = hashlib.sha256((record.path / "manifest.json").read_bytes()).hexdigest()
    payload = {"approval_version": APPROVAL_VERSION, "run_id": record.run_id,
               "manifest_sha256": manifest_hash, "decision": "approved",
               "reviewer": reviewer.strip(), "reviewed_at": reviewed_at,
               "rationale": rationale.strip()}
    approval_id = hashlib.sha256(_canonical(payload)).hexdigest()[:24]
    target = Path(approval_dir) / record.run_id / f"{approval_id}.json"
    content = _canonical({"approval_id": approval_id, **payload})
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != content:
        raise FileExistsError(f"immutable experiment approval differs: {target}")
    if not target.exists():
        target.write_bytes(content)
    return target
