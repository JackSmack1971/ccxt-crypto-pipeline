"""Deterministic discovery-only negative controls for experiment results."""

from __future__ import annotations

import random
from dataclasses import asdict, replace
from typing import Any

from .spec import NegativeControlPolicy

NEGATIVE_CONTROL_VERSION = "phase7-negative-controls-v1"


def _permuted(labels: tuple[Any, ...], seed: int) -> tuple[Any, ...]:
    complete = [row for row in labels if row.status == "COMPLETE" and row.value is not None]
    values = [row.value for row in complete]
    random.Random(seed).shuffle(values)
    replacements = {row.token_id: value for row, value in zip(complete, values)}
    return tuple(replace(row, value=replacements[row.token_id]) if row.token_id in replacements else row
                 for row in labels)


def _known_null(labels: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(replace(row, value=0.0) for row in labels
                 if row.status == "COMPLETE" and row.value is not None) + tuple(
                     row for row in labels if not (row.status == "COMPLETE" and row.value is not None))


def build_negative_control_evidence(*, selected_token_ids: frozenset[str], labels: tuple[Any, ...],
                                    horizon: str, turnover: float, costs: tuple[float, ...],
                                    min_coverage: float, policy: NegativeControlPolicy,
                                    score_candidate, baseline_families) -> dict[str, Any]:
    """Evaluate synthetic controls without changing the discovery selection."""
    controls = []
    for index in range(policy.permutations if "label_permutation" in policy.methods else 0):
        controls.append(("label_permutation", index, _permuted(labels, policy.seed + index)))
    if "known_null" in policy.methods:
        controls.append(("known_null", 0, _known_null(labels)))
    results = []
    for method, index, control_labels in controls:
        baselines = baseline_families(control_labels, horizon=horizon)
        candidate = score_candidate(
            f"negative_control:{method}:{index}", control_labels, horizon=horizon,
            selected=lambda row: row.token_id in selected_token_ids,
            baseline_mean=baselines["no_trade"]["mean_return"], turnover=turnover,
            costs=costs, min_coverage=min_coverage)
        results.append({"method": method, "index": index, "synthetic": True,
                        "selected_token_ids": sorted(selected_token_ids),
                        "candidate": asdict(candidate), "baseline": baselines["no_trade"]})
    return {"version": NEGATIVE_CONTROL_VERSION, "status": "available" if results else "unavailable",
            "reason": None if results else "NO_CONTROLS_CONFIGURED", "policy": policy.as_dict(),
            "selection_scope": "discovery_selected_candidate", "results": results}
