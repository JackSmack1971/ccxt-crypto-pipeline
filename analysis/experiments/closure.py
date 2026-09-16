"""Deterministic closure evidence for the configured robustness suite."""

from __future__ import annotations

import math
from typing import Any


CLOSURE_VERSION = "phase7-validation-closure-v1"


def _component(name: str, evidence: dict[str, Any], *, passed: bool | None,
               reason: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "version": evidence.get("version"),
        "status": "unavailable" if evidence.get("status") == "unavailable" else
                  "passed" if passed else "failed",
        "passed": passed is True,
        "reason": reason,
    }


def build_validation_closure(*, spec_id: str, selected_token_ids: frozenset[str],
                             promotion: dict[str, Any], uncertainty: dict[str, Any],
                             stress: dict[str, Any], stability: dict[str, Any],
                             negative_controls: dict[str, Any],
                             walk_forward: dict[str, Any] | None = None) -> dict[str, Any]:
    """Close one already-selected candidate against all configured robustness evidence.

    This function never selects, promotes, or reads another partition. A result
    can be ``passed`` only after holdout confirmation and a complete suite.
    """
    components: list[dict[str, Any]] = []
    promotion_state = promotion.get("state")
    if promotion_state != "holdout_confirmed":
        return {
            "version": CLOSURE_VERSION,
            "spec_id": spec_id,
            "selection_scope": "discovery_selected_candidate",
            "selected_token_ids": sorted(selected_token_ids),
            "status": "ineligible",
            "passed": False,
            "reason": "PROMOTION_NOT_HOLDOUT_CONFIRMED",
            "promotion_state": promotion_state,
            "components": components,
        }

    if walk_forward is not None:
        walk_forward_passed = walk_forward.get("status", "available") != "unavailable" and bool(
            walk_forward.get("folds")) and bool(walk_forward.get("results"))
        components.append(_component(
            "walk_forward", walk_forward, passed=walk_forward_passed,
            reason=None if walk_forward_passed else "WALK_FORWARD_EVIDENCE_UNAVAILABLE"))

    uncertainty_passed = (uncertainty.get("status") == "available" and
                          uncertainty.get("ci95_low") is not None)
    components.append(_component("uncertainty", uncertainty, passed=uncertainty_passed,
                                 reason=None if uncertainty_passed else "UNCERTAINTY_UNAVAILABLE"))

    stress_passed = stress.get("status", "available") != "unavailable" and stress.get("passed") is True
    components.append(_component("stress_matrix", stress, passed=stress_passed,
                                 reason=None if stress_passed else "STRESS_SCENARIO_FAILED"))

    stability_passed = stability.get("status") == "available" and not stability.get("dominated", False)
    components.append(_component("stability", stability, passed=stability_passed,
                                 reason=None if stability_passed else "STABILITY_DOMINANCE_OR_UNAVAILABLE"))

    controls = negative_controls.get("results", [])
    differences = [row.get("candidate", {}).get("baseline_comparison", {}).get("difference")
                   for row in controls]
    insufficient_controls = any(not isinstance(value, (int, float)) or not math.isfinite(value)
                                for value in differences)
    control_failures = [value for value in differences
                        if isinstance(value, (int, float)) and math.isfinite(value) and value > 0]
    controls_passed = (negative_controls.get("status") == "available" and bool(controls)
                       and not insufficient_controls and not control_failures)
    components.append(_component("negative_controls", negative_controls, passed=controls_passed,
                                 reason=None if controls_passed else
                                 "NEGATIVE_CONTROL_INSUFFICIENT_EVIDENCE" if insufficient_controls else
                                 "NEGATIVE_CONTROL_REJECTED"))

    failed = [item["name"] for item in components if item["status"] == "failed"]
    unavailable = [item["name"] for item in components if item["status"] == "unavailable"]
    reason = ("ROBUSTNESS_COMPONENT_FAILED" if failed else
              "ROBUSTNESS_COMPONENT_UNAVAILABLE" if unavailable else None)
    return {
        "version": CLOSURE_VERSION,
        "spec_id": spec_id,
        "selection_scope": "discovery_selected_candidate",
        "selected_token_ids": sorted(selected_token_ids),
        "status": "passed" if not failed and not unavailable else "failed" if failed else "unavailable",
        "passed": not failed and not unavailable,
        "reason": reason,
        "promotion_state": promotion_state,
        "components": components,
    }
