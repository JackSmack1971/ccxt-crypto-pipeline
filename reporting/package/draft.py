"""Optional, review-only model drafting from a validated claim ledger."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable


VERSION = "phase8-draft-v1"
_NUMBER = re.compile(r"(?<![A-Za-z])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:%|[A-Za-z]{0,4})?(?![A-Za-z])")
_COMPARATIVE = re.compile(
    r"\b(?:more|less|higher|lower|greater|smaller|increase|decrease|outperform(?:ed|s)?|"
    r"better|worse|versus|vs\.?|than|exceed(?:ed|s)?|surpass(?:ed|es)?)\b", re.I
)


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _manifest(package: Path) -> dict[str, Any]:
    manifest_path = package / "package-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("package manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("immutable") is not True or manifest.get("review_status") != "pending":
        raise ValueError("drafting requires an immutable pending-review package")
    if manifest.get("package_id") != package.name:
        raise ValueError("package identity mismatch")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("package lacks artifact hashes")
    for name, expected in artifacts.items():
        relative = Path(name)
        path = (package / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or package not in path.parents or not path.is_file():
            raise ValueError(f"invalid package artifact: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            if name == "claim-ledger.json":
                raise ValueError("claim ledger hash mismatch")
            raise ValueError(f"package artifact hash mismatch: {name}")
    if "claim-ledger.json" not in artifacts:
        raise ValueError("claim ledger hash mismatch")
    return manifest


def build_draft_request(package_dir: str | Path) -> dict[str, Any]:
    """Return the only input an assisted-drafting model is allowed to receive."""
    package = Path(package_dir).resolve()
    manifest = _manifest(package)
    ledger_bytes = (package / "claim-ledger.json").read_bytes()
    ledger = json.loads(ledger_bytes.decode())
    if not isinstance(ledger, list):
        raise ValueError("claim ledger must be a list")
    return {
        "draft_version": VERSION,
        "package_id": manifest.get("package_id"),
        "claim_ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "claims": ledger,
        "instructions": (
            "Write editorial connective prose only. Do not add facts, numbers, comparisons, "
            "sources, recommendations, or research conclusions. The deterministic report package "
            "remains the source of truth and this output is a review-only suggestion."
        ),
    }


def generate_assisted_draft(
    package_dir: str | Path,
    output_dir: str | Path,
    model: Callable[[str], str],
    *,
    model_id: str,
) -> Path:
    """Generate an isolated, immutable editorial suggestion from a claim ledger."""
    request = build_draft_request(package_dir)
    if not model_id.strip():
        raise ValueError("model_id is required")
    draft = model(json.dumps(request, sort_keys=True, separators=(",", ":")))
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("model returned an empty draft")
    if _NUMBER.search(draft) or _COMPARATIVE.search(draft):
        raise ValueError("assisted draft contains unsupported factual or comparative language")
    if re.search(r"(?i)(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]", draft):
        raise ValueError("assisted draft contains a secret-like value")

    output_root = Path(output_dir).resolve()
    draft_id = hashlib.sha256(_json({"request": request, "model_id": model_id, "draft": draft})).hexdigest()[:24]
    target = output_root / draft_id
    files = {
        "draft.md": draft.encode(),
        "draft-manifest.json": _json({
            "draft_version": VERSION, "draft_id": draft_id, "package_id": request["package_id"],
            "claim_ledger_sha256": request["claim_ledger_sha256"], "model_id": model_id,
            "review_status": "pending", "source_of_truth": "deterministic-package",
            "artifacts": {"draft.md": hashlib.sha256(draft.encode()).hexdigest()},
        }),
    }
    target.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = target / name
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"immutable draft artifact differs: {path}")
        if not path.exists():
            path.write_bytes(content)
    return target
