"""Deterministic, approved uncertainty estimators for experiment evidence."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class UncertaintyPolicy:
    """Configuration for the supported dependent-observation estimator."""

    version: str = "phase7-uncertainty-v1"
    method: str = "moving_block_bootstrap"
    dependence_structure: str = "ordered_blocks"
    resamples: int = 2000
    block_size: int = 3
    seed: int = 17

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("uncertainty policy requires a version")
        if self.method != "moving_block_bootstrap":
            raise ValueError(f"unsupported uncertainty method: {self.method}")
        if self.dependence_structure != "ordered_blocks":
            raise ValueError("moving block bootstrap requires ordered_blocks dependence")
        if type(self.resamples) is not int or self.resamples < 100:
            raise ValueError("uncertainty policy requires at least 100 resamples")
        if type(self.block_size) is not int or self.block_size < 1:
            raise ValueError("uncertainty block size must be positive")
        if type(self.seed) is not int:
            raise ValueError("uncertainty seed must be an integer")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    rank = fraction * (len(ordered) - 1)
    lower, upper = math.floor(rank), math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def bootstrap_mean(values: Iterable[float], policy: UncertaintyPolicy = UncertaintyPolicy()) -> dict[str, Any]:
    """Estimate a mean and percentile interval using deterministic moving blocks.

    Values must already be ordered by their declared observation time. No
    shuffle or imputation is performed; insufficient evidence stays unavailable.
    """
    ordered = [float(value) for value in values]
    if any(not math.isfinite(value) for value in ordered):
        raise ValueError("uncertainty values must be finite")
    result: dict[str, Any] = {"version": policy.version, "method": policy.method,
                              "dependence_structure": policy.dependence_structure,
                              "config": policy.as_dict(), "sample_size": len(ordered)}
    if not ordered:
        return {**result, "status": "unavailable", "reason": "NO_COMPLETE_OBSERVATIONS",
                "estimate": None, "ci95_low": None, "ci95_high": None}
    if len(ordered) < policy.block_size:
        return {**result, "status": "unavailable", "reason": "INSUFFICIENT_BLOCK_OBSERVATIONS",
                "estimate": sum(ordered) / len(ordered), "ci95_low": None, "ci95_high": None}

    rng = random.Random(policy.seed)
    means: list[float] = []
    starts = len(ordered) - policy.block_size + 1
    for _ in range(policy.resamples):
        sample: list[float] = []
        while len(sample) < len(ordered):
            start = rng.randrange(starts)
            sample.extend(ordered[start:start + policy.block_size])
        means.append(sum(sample[:len(ordered)]) / len(ordered))
    return {**result, "status": "available", "reason": None,
            "estimate": sum(ordered) / len(ordered),
            "ci95_low": _percentile(means, .025), "ci95_high": _percentile(means, .975)}
