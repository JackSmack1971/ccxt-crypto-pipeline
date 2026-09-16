"""Deterministic scientific benchmark corpus for offline methodology checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


BENCHMARK_VERSION = "phase8r-benchmark-v1"


@dataclass(frozen=True)
class BenchmarkCase:
    """One declared methodological behavior and its expected disposition."""

    case_id: str
    category: str
    expected_outcome: str
    purpose: str


_CASES = (
    BenchmarkCase("random_signal", "false_positive", "reject", "A random signal must not pass a promotion gate."),
    BenchmarkCase("future_feature", "temporal_leakage", "block", "A feature observed after decision time must be blocked."),
    BenchmarkCase("survivorship_biased_universe", "selection_bias", "reject", "A universe omitting dead assets must be rejected as biased."),
    BenchmarkCase("known_null", "negative_control", "pass", "A known-null control must show no candidate advantage."),
    BenchmarkCase("known_effect", "synthetic_effect", "pass", "A declared effect process must remain detectable."),
    BenchmarkCase("duplicate_observations", "data_integrity", "block", "Duplicate observations must fail closed."),
    BenchmarkCase("future_liquidity", "temporal_leakage", "block", "Liquidity observed after decision time must be blocked."),
    BenchmarkCase("insufficient_sample", "coverage", "reject", "Insufficient observations must not promote a candidate."),
    BenchmarkCase("discovery_only_overfit", "holdout_integrity", "reject", "Discovery-only overfit must fail confirmation."),
    BenchmarkCase("unstable_cross_source", "robustness", "reject", "Unstable provider or chain evidence must fail robustness."),
    BenchmarkCase("missing_conversion", "missingness", "block", "Missing quote conversion must remain unavailable."),
    BenchmarkCase("ambiguous_identity", "identity", "block", "Ambiguous identity evidence must fail closed."),
)


def benchmark_cases() -> tuple[BenchmarkCase, ...]:
    """Return the immutable, sorted benchmark contract."""
    return _CASES


def benchmark_identity() -> str:
    """Return the deterministic identity of the declared corpus."""
    payload = {"version": BENCHMARK_VERSION, "cases": [asdict(case) for case in _CASES]}
    return hashlib.sha256((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()[:24]


def verify_benchmark_results(results: dict[str, str]) -> None:
    """Fail unless every case has exactly its declared expected disposition."""
    expected = {case.case_id: case.expected_outcome for case in _CASES}
    if set(results) != set(expected):
        raise ValueError("benchmark results must contain exactly the declared cases")
    mismatches = sorted(case_id for case_id, outcome in results.items() if outcome != expected[case_id])
    if mismatches:
        raise ValueError("benchmark outcome mismatch: " + ", ".join(mismatches))


__all__ = ["BENCHMARK_VERSION", "BenchmarkCase", "benchmark_cases", "benchmark_identity", "verify_benchmark_results"]
