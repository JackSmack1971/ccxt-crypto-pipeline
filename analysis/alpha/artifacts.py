from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .report import research_report

def _plain(value: Any) -> Any:
    if hasattr(value, "as_artifact"): return _plain(value.as_artifact())
    if is_dataclass(value): return _plain(asdict(value))
    if isinstance(value, dict): return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [_plain(v) for v in value]
    return value

_SECRET = re.compile(r"(?i)(api[_-]?key|password|secret|token|private[_-]?key|rpc[_-]?url)\s*[:=]\s*[^\s,;]+")
_URL_CREDENTIAL = re.compile(r"(?i)(://)[^/\s:@]+:[^/\s@]+@")

def _safe(value: Any) -> Any:
    value = _plain(value)
    if isinstance(value, dict): return {k: "[REDACTED]" if re.search(r"(?i)(api[_-]?key|password|secret|token|private[_-]?key|rpc[_-]?url)$", k) else _safe(v) for k, v in value.items()}
    if isinstance(value, list): return [_safe(v) for v in value]
    if isinstance(value, str): return _SECRET.sub(r"\1=[REDACTED]", _URL_CREDENTIAL.sub(r"\1[REDACTED]@", value))
    return value

def _dump(value: Any) -> bytes:
    return (json.dumps(_safe(value), default=str, sort_keys=True, separators=(",", ":")) + "\n").encode()

def write_research_run(output_dir: str | Path, *, dataset_identity: str, cohort_config: Any,
                       cohort=(), features=(), labels=(), candidates=(), hypotheses=(), split=None,
                       report: str | None = None,
                       approved_chart_transformations: dict[str, Any] | None = None) -> Path:
    """Write immutable Phase 3 evidence files; reruns with identical inputs are byte-identical."""
    hypothesis_artifact = _plain(hypotheses)
    report_hypotheses = (hypothesis_artifact.get("hypotheses", [])
                         if isinstance(hypothesis_artifact, dict) else hypothesis_artifact)
    artifacts = {"cohort.json": cohort, "features.json": features, "labels.json": labels,
                 "candidates.json": candidates, "hypotheses.json": hypothesis_artifact,
                 "report.md": report if report is not None else research_report(cohort=cohort, labels=labels,
                    candidates=candidates, split=split, hypotheses=report_hypotheses,
                    dataset_identity=dataset_identity)}
    artifact_hashes = {name: hashlib.sha256(_dump(value)).hexdigest() for name, value in artifacts.items()}
    payload = {"dataset_identity": dataset_identity, "cohort_config": cohort_config, "split": split,
               "artifacts": artifact_hashes,
               "approved_chart_transformations": approved_chart_transformations or {}}
    run_id = hashlib.sha256(_dump(payload)).hexdigest()[:24]
    target = Path(output_dir) / run_id; target.mkdir(parents=True, exist_ok=True)
    manifest = {"manifest_version": "phase3-v1", "run_id": run_id, "immutable": True,
                "inputs": {"dataset_identity": dataset_identity, "cohort_config": cohort_config, "split": split},
                "artifacts": artifact_hashes}
    if approved_chart_transformations:
        manifest["approved_chart_transformations"] = approved_chart_transformations
    for name, value in {**artifacts, "manifest.json": manifest}.items():
        path = target / name; content = _dump(value)
        if path.exists() and path.read_bytes() != content: raise FileExistsError(f"immutable artifact differs: {path}")
        if not path.exists(): path.write_bytes(content)
    return target
