"""Deterministic, policy-bound falsification evidence."""

from __future__ import annotations

import math
from typing import Any

from .spec import FalsificationPolicy

FALSIFICATION_VERSION = "phase8r-falsification-v1"


def _control_status(evidence: dict[str, Any], method: str) -> tuple[str, str | None]:
    rows = [row for row in evidence.get("results", []) if row.get("method") == method]
    if evidence.get("status") != "available" or not rows:
        return "unavailable", "EVIDENCE_UNAVAILABLE"
    differences = [row.get("candidate", {}).get("baseline_comparison", {}).get("difference") for row in rows]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in differences):
        return "unavailable", "EVIDENCE_INCOMPLETE"
    return ("failed", "NULL_CONTROL_OUTPERFORMED_BASELINE") if any(value > 0 for value in differences) else ("passed", None)


def _leave_one_out_status(evidence: dict[str, Any]) -> tuple[str, str | None]:
    rows = evidence.get("dimensions", {}).get("leave_one_out")
    if evidence.get("status") != "available" or not isinstance(rows, list) or not rows:
        return "unavailable", "EVIDENCE_UNAVAILABLE"
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("excluded_token_id"), str) or
                type(row.get("remaining_sample_size")) is not int or row["remaining_sample_size"] < 0):
            return "unavailable", "EVIDENCE_INCOMPLETE"
        for key in ("mean_return", "baseline_mean_return"):
            value = row.get(key)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                return "unavailable", "EVIDENCE_INCOMPLETE"
    return "passed", None


def build_falsification_evidence(*, policy: FalsificationPolicy,
                                 negative_controls: dict[str, Any],
                                 stability: dict[str, Any]) -> dict[str, Any]:
    """Evaluate exactly the tests declared before results were produced.

    Unknown or missing implementations stay unavailable. Every declared test
    is required, preventing post-result selection of a favorable subset.
    """
    results: list[dict[str, Any]] = []
    for method in policy.methods:
        if method in policy.inapplicable_methods:
            status, reason, evidence_ref = "inapplicable", "NOT_APPLICABLE_TO_DECLARED_UNIVERSE", None
        elif method in {"label_permutation", "known_null"}:
            status, reason = _control_status(negative_controls, method)
            evidence_ref = "negative_controls.json"
        elif method == "leave_one_out":
            status, reason = _leave_one_out_status(stability)
            evidence_ref = "stability.json"
        else:
            status, reason, evidence_ref = "unavailable", "METHOD_NOT_IMPLEMENTED", None
        results.append({"method": method, "status": status, "reason": reason,
                        "evidence_ref": evidence_ref})
    return {"version": FALSIFICATION_VERSION, "policy": policy.as_dict(),
            "status": "passed" if all(row["status"] == "passed" for row in results) else
                      "failed" if any(row["status"] == "failed" for row in results) else
                      "inapplicable" if any(row["status"] == "inapplicable" for row in results) else "unavailable",
            "results": results, "selection": "all_declared_methods_required"}
