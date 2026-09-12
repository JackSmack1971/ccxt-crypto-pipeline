from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from reporting.charts.spec import validate_chart
from reporting.claims.model import validate_claims
from reporting.render.static import RENDERER_VERSION, render_svg, validate_accessibility
from .handoff import validate_approved_handoff


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode()


def _read(path: Path) -> Any:
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_input_path(root: Path, relative_value: str, label: str) -> Path:
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} escapes input package")
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError(f"{label} escapes input package")
    return path


def _safe_chart_id(value: str) -> str:
    path = Path(value)
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) or
            path.is_absolute() or len(path.parts) != 1 or path.name in {".", ".."}):
        raise ValueError("chart id must be a safe relative filename")
    return value


def _safe_output_path(root: Path, relative: str) -> Path:
    path = root / relative
    resolved_root = root.resolve()
    if not path.resolve().is_relative_to(resolved_root):
        raise ValueError("output artifact escapes package")
    return path


def _verified_digest(path: Path, expected: str, label: str) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"{label} content hash mismatch")


def _security_scan(values: Any) -> None:
    text = json.dumps(values, default=str, sort_keys=True)
    patterns = (r"(?i)sk-[A-Za-z0-9_-]{10,}", r"(?i)(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]\s*[^\s,;]+",
                r"(?i)://[^/\s:@]+:[^/\s@]+@", r"(?i)https?://[^\s]+(?:api[_-]?key|token|secret)=",
                r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]+",
                r"(?i)https?://(?:[^/\s]+\.)?(?:alchemy\.com|infura\.io|quicknode\.com|helius-rpc\.com)(?:/[^\s\"']+)?",
                r"(?:[A-Za-z]:\\|/(?:Users|home|tmp|var)/)[^\s\"']+")
    if any(re.search(pattern, text) for pattern in patterns):
        raise ValueError("generated artifact contains a secret or secret-bearing URL")


def _load_staged(root: Path, manifest: dict[str, Any], linked_artifacts: dict[str, dict[str, str]]) -> dict[str, Any]:
    staged = {}
    for name in sorted(manifest.get("staged_tables", {})):
        entry = manifest["staged_tables"][name]
        if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
            raise ValueError(f"staged table lacks a content hash: {name}")
        path = _safe_input_path(root, entry["path"], f"staged table {name}")
        _verified_digest(path, entry["sha256"], f"staged table {name}")
        if not any(entry["sha256"] == linked["sha256"] and entry["path"] == linked["path"]
                   for linked in linked_artifacts.values()):
            raise ValueError(f"staged table {name} is not a declared Phase 3 artifact")
        staged[name] = _read(path)
    return staged


def _validate_research_link(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    link = manifest.get("research_run")
    if not isinstance(link, dict) or not link.get("path") or not link.get("sha256"):
        raise ValueError("approved manifest lacks a hash-verified research manifest")
    path = _safe_input_path(root, link["path"], "research manifest")
    _verified_digest(path, link["sha256"], "research manifest")
    research = _read(path)
    if research.get("manifest_version") != "phase3-v1" or research.get("immutable") is not True:
        raise ValueError("research manifest is not an immutable Phase 3 artifact")
    if not research.get("run_id") or not isinstance(research.get("artifacts"), dict):
        raise ValueError("research manifest lacks run identity or artifact hashes")
    expected_dataset = manifest.get("dataset_identity")
    if research.get("inputs", {}).get("dataset_identity") != expected_dataset:
        raise ValueError("approved manifest dataset does not match research manifest")
    if manifest.get("approved_chart_transformations", {}) != research.get("approved_chart_transformations", {}):
        raise ValueError("chart transformations are not authorized by the Phase 3 result")
    linked = manifest.get("research_artifacts")
    if not isinstance(linked, dict) or not linked:
        raise ValueError("approved manifest lacks linked research artifacts")
    linked_hashes = {}
    for name, entry in linked.items():
        if name not in research["artifacts"] or not isinstance(entry, dict):
            raise ValueError(f"research artifact is not declared by Phase 3: {name}")
        artifact_path = _safe_input_path(root, entry.get("path", ""), f"research artifact {name}")
        _verified_digest(artifact_path, entry.get("sha256", ""), f"research artifact {name}")
        if entry["sha256"] != research["artifacts"][name]:
            raise ValueError(f"research artifact does not match Phase 3 manifest: {name}")
        linked_hashes[name] = {"path": entry["path"], "sha256": entry["sha256"]}
    if link.get("run_id") != research["run_id"]:
        raise ValueError("approved manifest research-run identity does not match the linked artifact")
    return {"run_id": research["run_id"], "manifest_sha256": link["sha256"],
            "artifacts": linked_hashes}


def generate_package(input_dir: str | Path, output_dir: str | Path) -> Path:
    """Build a pending human-review package from one immutable approved input."""
    root = Path(input_dir).resolve()
    manifest = _read(root / "manifest.json")
    validate_approved_handoff(manifest)
    if not manifest.get("immutable") or manifest.get("approved") is not True:
        raise ValueError("Phase 4 requires an immutable approved manifest")
    approval = manifest.get("approval")
    if not isinstance(approval, dict) or approval.get("status") != "approved" or not approval.get("reviewer"):
        raise ValueError("Phase 4 requires explicit approval metadata")
    research_link = _validate_research_link(root, manifest)
    staged = _load_staged(root, manifest, research_link["artifacts"])
    _security_scan(manifest)
    claims = validate_claims(manifest.get("claims", ()), manifest, staged)
    charts = [validate_chart(item, staged, manifest.get("approved_chart_transformations"), manifest)
              for item in manifest.get("charts", ())]
    chart_ids = [_safe_chart_id(chart["id"]) for chart in charts]
    if len(set(chart_ids)) != len(chart_ids):
        raise ValueError("chart ids must be unique")
    for chart in charts:
        rows = staged[chart["data_artifact"]]
        svg = render_svg(chart, rows)
        validate_accessibility(svg, chart)
        chart["_svg"] = svg
    inputs = {"manifest_identity": manifest["handoff_id"],
              "research_run_id": research_link["run_id"], "research_manifest_sha256": research_link["manifest_sha256"],
              "dataset_identity": manifest.get("dataset_identity", manifest.get("inputs", {}).get("dataset_identity", "unknown")),
              "code_version": manifest.get("code_version", "unknown"), "config_identity": manifest.get("config_identity", "unknown"),
              "query_config_identity": manifest.get("query_config_identity", "unknown"),
              "approval": manifest.get("approval", {}),
              "time_range": manifest.get("time_range", manifest.get("inputs", {}).get("time_range", {})),
              "human_review": "required"}
    methodology = manifest.get("methodology", {})
    method_lines = ["## Methodology and limitations", f"- Cohort/split: {methodology.get('cohort_split', 'not supplied')}",
                    f"- Time range: {inputs['time_range']}", f"- Costs: {methodology.get('costs', 'not supplied')}",
                    f"- Missingness: {methodology.get('missingness', 'not supplied')}", f"- Uncertainty: {methodology.get('uncertainty', 'not supplied')}",
                    f"- Limitations: {methodology.get('limitations', 'not supplied')}"]
    article = "\n".join([f"# {manifest.get('title', 'Research results')}", "", *[f"{c['text']}" for c in claims], "", *method_lines, ""])
    _security_scan({"article": article, "claims": claims, "methodology": methodology})
    package_key = hashlib.sha256(_json({"manifest": manifest, "claims": claims, "charts": [{k:v for k,v in c.items() if k != "_svg"} for c in charts]})).hexdigest()[:24]
    output_root = Path(output_dir).resolve()
    target = _safe_output_path(output_root, package_key)
    target.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {"article.md": article.encode(), "claim-ledger.json": _json(claims),
                               "chart-specs.json": _json([{k:v for k,v in c.items() if k != "_svg"} for c in charts]),
                               "methodology-limitations.md": ("\n".join(method_lines) + "\n").encode(),
                               "review.json": _json({"status": "pending", "approval_required": True, "package_id": package_key})}
    for chart in charts:
        files[f"charts/{_safe_chart_id(chart['id'])}.svg"] = chart.pop("_svg").encode()
    checksums = {}
    for name, content in sorted(files.items()):
        path = _safe_output_path(target, name); path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"immutable package artifact differs: {path}")
        if not path.exists(): path.write_bytes(content)
        checksums[name] = hashlib.sha256(content).hexdigest()
    unexpected = [p for p in target.rglob("*") if p.is_file() and
                  p.relative_to(target).as_posix() not in checksums and p.name != "package-manifest.json"]
    if unexpected:
        raise FileExistsError(f"immutable package contains unexpected artifacts: {unexpected[0].name}")
    package_manifest = {"package_version": "phase4-v1", "package_id": package_key, "immutable": True,
                        "review_status": "pending", "inputs": inputs, "renderer_version": RENDERER_VERSION,
                        "chart_semantics": {c["id"]: {"transformations": c.get("transformations", ()),
                                                       "annotations": c.get("annotations", ())} for c in charts},
                        "staged_inputs": manifest.get("staged_tables", {}),
                        "artifacts": checksums, "validation": {"claims": "passed", "charts": "passed", "accessibility": "passed"}}
    _security_scan(package_manifest)
    path = target / "package-manifest.json"; content = _json(package_manifest)
    if path.exists() and path.read_bytes() != content: raise FileExistsError(f"immutable package manifest differs: {path}")
    if not path.exists(): path.write_bytes(content)
    return target
