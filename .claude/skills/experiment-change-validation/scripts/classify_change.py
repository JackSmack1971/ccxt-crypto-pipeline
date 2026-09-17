#!/usr/bin/env python3
"""Deterministically map changed repository paths to minimum methodology contract families.

This is intentionally conservative: it establishes a minimum set of affected contracts.
The skill must still inspect code/diffs for transitive effects.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("point_in_time", ("analysis/datasets/", "analysis/alpha/features.py", "analysis/alpha/evaluation.py"), ("tests/test_phase3.py",)),
    ("cohort_eligibility", ("analysis/alpha/cohort.py", "analysis/alpha/eligibility.py"), ("tests/test_eligibility.py", "tests/test_phase3.py")),
    ("feature_semantics", ("analysis/alpha/features.py", "analysis/alpha/registry.py"), ("tests/test_phase3.py",)),
    ("label_semantics", ("analysis/alpha/labels.py",), ("tests/test_phase3.py",)),
    ("split_leakage", ("analysis/alpha/evaluation.py", "analysis/experiments/spec.py", "analysis/experiments/walk_forward.py"), ("tests/test_phase3.py", "tests/test_phase6.py")),
    ("promotion_holdout", ("analysis/alpha/evaluation.py", "analysis/experiments/control.py"), ("tests/test_phase3.py", "tests/test_phase6.py")),
    ("multiplicity_hypotheses", ("analysis/experiments/hypotheses.py", "analysis/experiments/spec.py"), ("tests/test_phase6.py",)),
    ("candidate_scoring", ("analysis/experiments/runner.py", "analysis/experiments/spec.py"), ("tests/test_phase6.py",)),
    ("uncertainty_censoring", ("analysis/experiments/uncertainty.py", "analysis/alpha/eligibility.py", "analysis/alpha/evaluation.py"), ("tests/test_phase6.py", "tests/test_phase3.py")),
    ("backtest_execution", ("analysis/backtesting/", "analysis/strategies/", "analysis/metrics/", "analysis/runs/"), ("tests/test_phase2.py",)),
    ("experiment_spec_identity", ("analysis/experiments/spec.py",), ("tests/test_phase6.py",)),
    ("run_artifact_identity", ("analysis/alpha/artifacts.py", "analysis/experiments/catalog.py", "analysis/experiments/runner.py", "analysis/runs/"), ("tests/test_phase3.py", "tests/test_phase6.py")),
    ("compatibility", ("analysis/alpha/registry.py", "analysis/alpha/evaluation.py", "analysis/experiments/spec.py"), ("tests/test_phase3.py", "tests/test_phase6.py")),
    ("offline_boundary", ("analysis/",), ()),
]


def norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def matches(path: str, pattern: str) -> bool:
    path, pattern = norm(path), norm(pattern)
    return path.startswith(pattern) if pattern.endswith("/") else path == pattern


def git_paths(repo: Path) -> list[str]:
    commands = [
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    paths: set[str] = set()
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=repo, text=True, capture_output=True)
        if proc.returncode != 0:
            raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
        paths.update(norm(line) for line in proc.stdout.splitlines() if line.strip())
    return sorted(paths)


def classify(paths: list[str]) -> dict[str, object]:
    normalized = sorted({norm(p) for p in paths})
    contracts: dict[str, dict[str, object]] = {}
    tests: set[str] = set()
    for family, patterns, anchors in RULES:
        hits = [p for p in normalized if any(matches(p, pattern) for pattern in patterns)]
        if hits:
            contracts[family] = {"paths": hits, "focused_test_anchors": list(anchors)}
            tests.update(anchors)

    methodology = any(p.startswith("analysis/alpha/") or p.startswith("analysis/experiments/") or
                      p.startswith("analysis/backtesting/") or p.startswith("analysis/strategies/") or
                      p.startswith("analysis/metrics/") or p.startswith("analysis/runs/")
                      for p in normalized)
    return {
        "methodology_surface_detected": methodology,
        "paths": normalized,
        "contract_families": contracts,
        "minimum_focused_test_anchors": sorted(tests),
        "note": "Minimum deterministic map only; inspect diffs for transitive contracts before declaring UNAFFECTED.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", help="repository root used when --path is omitted")
    parser.add_argument("--path", action="append", default=[], help="changed path; repeatable")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    paths = args.path or git_paths(Path(args.repo).resolve())
    result = classify(paths)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("methodology_surface_detected:", str(result["methodology_surface_detected"]).lower())
        for family, item in result["contract_families"].items():
            print(f"{family}: {', '.join(item['paths'])}")
        if result["minimum_focused_test_anchors"]:
            print("focused test anchors:")
            for test in result["minimum_focused_test_anchors"]:
                print(f"  python -m pytest {test}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
