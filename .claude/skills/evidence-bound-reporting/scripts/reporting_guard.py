#!/usr/bin/env python3
"""Deterministic guardrails for the evidence-bound reporting skill.

This helper intentionally checks only mechanical invariants. It does not prove that a
claim derivation or chart transformation is semantically correct; repository tests must
prove those behaviors.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

FORBIDDEN_IMPORT_ROOTS = {
    "ingestion",
    "requests",
    "httpx",
    "aiohttp",
    "ccxt",
    "socket",
    "websocket",
    "websockets",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]\s*[^\s,;\"']+"),
    re.compile(r"(?i)://[^/\s:@]+:[^/\s@]+@"),
    re.compile(r"(?i)https?://[^\s]+(?:api[_-]?key|token|secret)="),
)
LOCAL_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:\\(?:Users|Documents|Desktop|AppData)\\", re.I),
    re.compile(r"/(?:Users|home|tmp|var)/(?:[^\s\"'<>]+)"),
)
NUMERIC_OR_COMPARE = re.compile(
    r"(?<![A-Za-z])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:%|[A-Za-z]{0,4})?(?![A-Za-z])"
    r"|\b(?:more|less|higher|lower|greater|smaller|increase|decrease|outperform|better|worse|versus|vs\.?|than)\b",
    re.I,
)


class GuardError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return ()
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def check_reporting_imports(repo: Path) -> list[str]:
    errors: list[str] = []
    reporting = repo / "reporting"
    if not reporting.is_dir():
        return ["reporting/ directory is missing"]
    for path in _python_files(reporting):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(repo)} cannot be parsed: {exc}")
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                root = name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    errors.append(f"{path.relative_to(repo)} imports forbidden reporting dependency {name!r}")
    return errors


def _scan_text(label: str, text: str) -> list[str]:
    errors: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{label} contains secret/credential-shaped content")
            break
    for pattern in LOCAL_PATH_PATTERNS:
        if pattern.search(text):
            errors.append(f"{label} contains an unintended local filesystem path")
            break
    return errors


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # precise message matters more than exception taxonomy here
        raise GuardError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise GuardError(f"{label} must be a JSON object")
    return value


def _check_svg(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path.name} is not valid SVG/XML: {exc}"]
    tag = root.tag.rsplit("}", 1)[-1]
    if tag != "svg":
        errors.append(f"{path.name} root element is not svg")
    if root.attrib.get("role") != "img":
        errors.append(f"{path.name} lacks role=img")
    child_names = [child.tag.rsplit("}", 1)[-1] for child in root]
    if "title" not in child_names:
        errors.append(f"{path.name} lacks <title>")
    if "desc" not in child_names:
        errors.append(f"{path.name} lacks <desc>")
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local == "script":
            errors.append(f"{path.name} contains script content")
        for key, value in element.attrib.items():
            if key.rsplit("}", 1)[-1] in {"href", "src"} and re.match(r"(?i)(?:https?|file):", value):
                errors.append(f"{path.name} contains external/file reference {value!r}")
    return errors


def check_package(package: Path) -> list[str]:
    errors: list[str] = []
    if not package.is_dir():
        return [f"package directory does not exist: {package}"]
    manifest_path = package / "package-manifest.json"
    review_path = package / "review.json"
    if not manifest_path.is_file():
        return ["package-manifest.json is missing"]
    if not review_path.is_file():
        errors.append("review.json is missing")
    try:
        manifest = _read_json(manifest_path, "package-manifest.json")
    except GuardError as exc:
        return [str(exc)]
    if manifest.get("immutable") is not True:
        errors.append("package manifest is not immutable")
    if manifest.get("review_status") != "pending":
        errors.append("package review_status must remain pending")
    validation = manifest.get("validation")
    if not isinstance(validation, dict):
        errors.append("package manifest lacks validation object")
    elif any(value != "passed" for value in validation.values()):
        errors.append("package manifest contains non-passing validation state")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        errors.append("package manifest lacks artifact checksums")
        artifacts = {}
    for relative, expected in sorted(artifacts.items()):
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts:
            errors.append(f"artifact path escapes package: {relative}")
            continue
        path = package / rel
        if not path.is_file():
            errors.append(f"declared artifact is missing: {relative}")
            continue
        actual = _sha256(path)
        if actual != expected:
            errors.append(f"artifact checksum mismatch: {relative}")
    if review_path.is_file():
        try:
            review = _read_json(review_path, "review.json")
            if review.get("status") != "pending" or review.get("approval_required") is not True:
                errors.append("review.json must remain pending with approval_required=true")
        except GuardError as exc:
            errors.append(str(exc))
    for path in sorted(p for p in package.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        errors.extend(_scan_text(path.relative_to(package).as_posix(), text))
        if path.suffix.lower() == ".svg":
            errors.extend(_check_svg(path))
    return errors


def check_claim_ledger_shape(package: Path) -> list[str]:
    """Defense-in-depth warning checks without assuming the repo's derivation schema.

    We deliberately do not require a field named `derivation`; the repository owns that
    schema. We only flag factual numeric/comparative claims that have no evidence at all.
    """
    path = package / "claim-ledger.json"
    if not path.is_file():
        return ["claim-ledger.json is missing"]
    try:
        claims = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"claim-ledger.json is not valid JSON: {exc}"]
    if not isinstance(claims, list):
        return ["claim-ledger.json must be a list"]
    errors: list[str] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claim {index} is not an object")
            continue
        if claim.get("kind", "fact") == "fact" and NUMERIC_OR_COMPARE.search(str(claim.get("text", ""))):
            if not claim.get("evidence"):
                errors.append(f"factual numeric/comparative claim {claim.get('id', index)!r} lacks evidence")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path, help="ccxt-crypto-pipeline repository root")
    parser.add_argument("--package", type=Path, help="optional generated Phase 4 package to inspect")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    errors = check_reporting_imports(repo)
    if args.package:
        package = args.package.resolve()
        errors.extend(check_package(package))
        errors.extend(check_claim_ledger_shape(package))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: mechanical evidence-bound reporting guards satisfied")
    if not args.package:
        print("NOTE: no package supplied; checksum/review/security/SVG package checks were not run")
    print("NOTE: semantic claim derivation and chart-transform correctness still require repository tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
