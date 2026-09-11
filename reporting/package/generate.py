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


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode()


def _read(path: Path) -> Any:
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    return json.loads(path.read_text(encoding="utf-8"))


def _security_scan(values: Any) -> None:
    text = json.dumps(values, default=str, sort_keys=True)
    patterns = (r"(?i)sk-[A-Za-z0-9_-]{10,}", r"(?i)(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]\s*[^\s,;]+",
                r"(?i)://[^/\s:@]+:[^/\s@]+@", r"(?i)https?://[^\s]+(?:api[_-]?key|token|secret)=",
                r"(?:[A-Za-z]:\\|/(?:Users|home|tmp|var)/)[^\s\"']+")
    if any(re.search(pattern, text) for pattern in patterns):
        raise ValueError("generated artifact contains a secret or secret-bearing URL")


def _load_staged(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    staged = {}
    for name in sorted(manifest.get("staged_tables", {})):
        relative = Path(manifest["staged_tables"][name])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"staged table escapes input package: {name}")
        path = (root / relative).resolve()
        if root.resolve() not in path.parents:
            raise ValueError(f"staged table escapes input package: {name}")
        staged[name] = _read(path)
    return staged


def generate_package(input_dir: str | Path, output_dir: str | Path) -> Path:
    """Build a pending human-review package from one immutable approved input."""
    root = Path(input_dir).resolve()
    manifest = _read(root / "manifest.json")
    if not manifest.get("immutable") or manifest.get("approved") is not True:
        raise ValueError("Phase 4 requires an immutable approved manifest")
    staged = _load_staged(root, manifest)
    _security_scan(manifest)
    claims = validate_claims(manifest.get("claims", ()), manifest, staged)
    charts = [validate_chart(item, staged) for item in manifest.get("charts", ())]
    for chart in charts:
        rows = staged[chart["data_artifact"]]
        svg = render_svg(chart, rows)
        validate_accessibility(svg, chart)
        chart["_svg"] = svg
    inputs = {"manifest_identity": manifest.get("manifest_identity", manifest.get("run_id", "approved")),
              "dataset_identity": manifest.get("dataset_identity", manifest.get("inputs", {}).get("dataset_identity", "unknown")),
              "code_version": manifest.get("code_version", "unknown"), "config_identity": manifest.get("config_identity", "unknown"),
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
    target = Path(output_dir) / package_key
    target.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {"article.md": article.encode(), "claim-ledger.json": _json(claims),
                               "chart-specs.json": _json([{k:v for k,v in c.items() if k != "_svg"} for c in charts]),
                               "methodology-limitations.md": ("\n".join(method_lines) + "\n").encode(),
                               "review.json": _json({"status": "pending", "approval_required": True, "package_id": package_key})}
    for chart in charts:
        files[f"charts/{chart['id']}.svg"] = chart.pop("_svg").encode()
    checksums = {}
    for name, content in sorted(files.items()):
        path = target / name; path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"immutable package artifact differs: {path}")
        if not path.exists(): path.write_bytes(content)
        checksums[name] = hashlib.sha256(content).hexdigest()
    package_manifest = {"package_version": "phase4-v1", "package_id": package_key, "immutable": True,
                        "review_status": "pending", "inputs": inputs, "renderer_version": RENDERER_VERSION,
                        "artifacts": checksums, "validation": {"claims": "passed", "charts": "passed", "accessibility": "passed"}}
    _security_scan(package_manifest)
    path = target / "package-manifest.json"; content = _json(package_manifest)
    if path.exists() and path.read_bytes() != content: raise FileExistsError(f"immutable package manifest differs: {path}")
    if not path.exists(): path.write_bytes(content)
    return target
