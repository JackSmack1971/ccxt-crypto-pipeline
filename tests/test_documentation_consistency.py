"""Checks for drift in selected, objectively verifiable public facts."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

SCHEMA_DOCUMENTS = (
    "docs/ARCHITECTURE.md",
    "docs/durable-invariants.md",
    "docs/architectural-constraints.md",
    "docs/verification-expectations.md",
    "ROADMAP.md",
)
PYTHON_DOCUMENTS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/RUNBOOK.md",
    "docs/operator-rules.md",
)
PHASE_DOCUMENTS = (
    "README.md",
    "docs/VISION.md",
)


def _schema_version(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SCHEMA_VERSION"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, int):
                return value
    raise AssertionError(f"{path}: authoritative SCHEMA_VERSION assignment not found")


def _minimum_python_version(path: Path) -> tuple[int, int]:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    match = re.fullmatch(r">=(\d+)\.(\d+)", project["requires-python"])
    if match is None:
        raise AssertionError(
            f"{path}: unsupported requires-python format {project['requires-python']!r}"
        )
    return int(match.group(1)), int(match.group(2))


def _roadmap_states(text: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for phase in ("8", "8R", "9", "10"):
        match = re.search(
            rf"^# Phase {re.escape(phase)}\b.*?^\*\*Status:\*\*\s*(\w+)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        if match is None:
            raise AssertionError(f"ROADMAP.md: status for Phase {phase} not found")
        states[phase] = match.group(1).upper()

    current = re.search(r"^\*\*Current phase:\*\*\s*(.+)$", text, re.MULTILINE)
    if current is None:
        raise AssertionError("ROADMAP.md: current phase declaration not found")
    states["current"] = current.group(1).strip().lower()
    return states


def documentation_errors(
    root: Path, *, overrides: dict[str, str] | None = None
) -> list[str]:
    """Return consistency errors, optionally replacing docs with fixture text."""
    overrides = overrides or {}

    def document(relative: str) -> str:
        if relative in overrides:
            return overrides[relative]
        path = root / relative
        return path.read_text(encoding="utf-8")

    schema_version = _schema_version(root / "storage/schema.py")
    python_version = _minimum_python_version(root / "pyproject.toml")
    errors: list[str] = []

    for relative in SCHEMA_DOCUMENTS:
        text = document(relative)
        if relative == "ROADMAP.md":
            pattern = r"Phase 1 ingestion/storage:.*?schema version\s+(\d+)"
        elif relative == "docs/verification-expectations.md":
            pattern = r"SCHEMA_VERSION\s*==\s*(\d+)"
        else:
            pattern = r"SCHEMA_VERSION\s*=\s*(\d+)"
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match is not None and int(match.group(1)) != schema_version:
            errors.append(
                f"{relative}: documented schema version {match.group(1)} "
                f"does not match storage/schema.py SCHEMA_VERSION {schema_version}"
            )

    for relative in PYTHON_DOCUMENTS:
        matches = re.findall(r"Python\s+([0-9]+)\.([0-9]+)", document(relative), re.IGNORECASE)
        if matches and any((int(major), int(minor)) != python_version for major, minor in matches):
            found = ", ".join(f"{major}.{minor}" for major, minor in matches)
            errors.append(
                f"{relative}: documented Python versions {found} do not match "
                f"pyproject.toml requires-python >= {python_version[0]}.{python_version[1]}"
            )

    roadmap = _roadmap_states(document("ROADMAP.md"))
    expected_mentions = {
        "Phase 8 completion": (r"Phase 8\b.{0,180}\b(?:complete|completed)", roadmap["8"] == "DONE"),
        "Phase 8R active frontier": (
            r"(?:Phase 8R\b.{0,180}\bactive|active.{0,180}\bPhase 8R\b)",
            roadmap["current"].startswith("phase 8r"),
        ),
        "Phase 9 deferred": (r"Phase 9\b.{0,180}\bdeferred", roadmap["9"] == "DEFERRED"),
        "Phase 10 deferred": (r"Phase 10\b.{0,180}\bdeferred", roadmap["10"] == "DEFERRED"),
    }
    for relative in PHASE_DOCUMENTS:
        text = document(relative)
        for fact, (pattern, should_check) in expected_mentions.items():
            if should_check and re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is None:
                errors.append(f"{relative}: does not reflect roadmap fact {fact}")

    return errors


def test_public_documentation_matches_authoritative_facts() -> None:
    errors = documentation_errors(Path(__file__).parents[1])
    assert not errors, "Documentation consistency errors:\n- " + "\n- ".join(errors)


def test_documentation_guard_reports_a_stale_schema_version() -> None:
    errors = documentation_errors(
        Path(__file__).parents[1],
        overrides={"docs/ARCHITECTURE.md": "`storage/schema.py` owns SCHEMA_VERSION = 12"},
    )
    assert any(
        "docs/ARCHITECTURE.md" in error and "SCHEMA_VERSION 13" in error
        for error in errors
    )
