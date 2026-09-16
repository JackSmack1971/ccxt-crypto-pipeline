"""Deterministic, offline robustness stress evidence for one fixed candidate."""

from __future__ import annotations

import math
from typing import Any

from .spec import StressPolicy


STRESS_MATRIX_VERSION = "phase7-stress-matrix-v1"


def _build_stress_matrix(*, selected_token_ids: frozenset[str], labels: tuple[Any, ...],
                         feature_rows: tuple[dict[str, Any], ...], horizon: str,
                         turnover: float, policy: StressPolicy) -> dict[str, Any]:
    """Evaluate approved scenarios without recomputing candidate membership.

    The input selection is already frozen by the discovery partition.  This
    function only filters and reprices those ids; it never reads holdout rows
    or creates a new threshold.
    """
    features = {row["token_id"]: row for row in feature_rows}
    target = {row.token_id: row for row in labels if row.horizon == horizon
              and row.token_id in selected_token_ids}
    missing_ids = sorted(selected_token_ids - set(target))
    rows = []
    for fee_rate in policy.fee_rates:
        for slippage_bps in policy.slippage_bps:
            for liquidity in policy.minimum_liquidity_usd:
                for missingness_mode in policy.missingness_modes:
                    eligible = [row for token_id, row in sorted(target.items())
                                if (features.get(token_id, {}).get("launch_liquidity_usd") is not None
                                    and features[token_id]["launch_liquidity_usd"] >= liquidity)]
                    ineligible_liquidity = sorted(set(target) - {row.token_id for row in eligible})
                    incomplete = sorted(row.token_id for row in eligible
                                        if row.status != "COMPLETE" or row.value is None)
                    invalid = sorted(row.token_id for row in eligible
                                     if row.status == "COMPLETE" and isinstance(row.value, (int, float))
                                     and not math.isfinite(row.value))
                    unavailable = missing_ids or invalid or (incomplete if missingness_mode == "fail_closed" else [])
                    complete = [row for row in eligible
                                if row.token_id not in incomplete and row.token_id not in invalid]
                    gross = (sum(float(row.value) for row in complete) / len(complete)
                             if complete and not unavailable else None)
                    cost_rate = fee_rate + slippage_bps / 10_000
                    net = gross - turnover * cost_rate if gross is not None else None
                    reason = None
                    if unavailable:
                        reason = ("INVALID_NONFINITE_LABEL" if invalid else
                                  "MISSINGNESS_FAIL_CLOSED" if incomplete and missingness_mode == "fail_closed"
                                  else "MISSING_LABEL_EVIDENCE")
                    elif not complete:
                        reason = "NO_COMPLETE_OBSERVATIONS"
                    rows.append({
                        "fee_rate": fee_rate, "slippage_bps": slippage_bps,
                        "minimum_liquidity_usd": liquidity, "missingness_mode": missingness_mode,
                        "status": "unavailable" if reason else "available",
                        "reason": reason, "sample_size": len(complete),
                        "missingness": (len(incomplete) + len(invalid) + len(missing_ids)) / len(selected_token_ids)
                        if selected_token_ids else 1.0,
                        "liquidity_excluded_token_ids": ineligible_liquidity,
                        "gross_mean_return": gross, "net_mean_return": net,
                        "passed": net is not None and math.isfinite(net) and net > 0,
                    })
    return {"version": STRESS_MATRIX_VERSION, "policy": policy, "horizon": horizon,
            "turnover": turnover, "selected_token_ids": sorted(selected_token_ids),
            "scenarios": rows,
            "passed": bool(rows) and all(row["passed"] for row in rows)}
