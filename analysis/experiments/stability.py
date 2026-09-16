"""Deterministic, discovery-only robustness evidence for subgroup concentration."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from .spec import StabilityPolicy

STABILITY_VERSION = "phase7-stability-v1"


def _mean(rows: list[Any]) -> float | None:
    values = [row.value for row in rows if row.status == "COMPLETE" and
              isinstance(row.value, (int, float)) and math.isfinite(row.value)]
    return sum(values) / len(values) if values else None


def _valid(row: Any) -> bool:
    return row.status == "COMPLETE" and isinstance(row.value, (int, float)) and math.isfinite(row.value)


def _observed_at_or_before(item: dict[str, Any], point: datetime) -> bool:
    try:
        observed = datetime.fromisoformat(str(item.get("timestamp", "")).replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is not None:
        observed = observed.astimezone(UTC).replace(tzinfo=None)
    if point.tzinfo is not None:
        point = point.astimezone(UTC).replace(tzinfo=None)
    return observed <= point


def _group_summary(name: str, rows: list[Any], total: int, threshold: float, minimum_group_size: int) -> dict[str, Any]:
    mean = _mean(rows)
    absolute = sum(abs(float(row.value)) for row in rows if _valid(row))
    all_absolute = sum(abs(float(row.value)) for row in rows if _valid(row))
    share = absolute / all_absolute if all_absolute else None
    return {"group": name, "sample_size": len(rows), "complete_sample_size": sum(
        1 for row in rows if _valid(row)),
        "mean_return": mean, "absolute_return_share": share,
        "sample_share": len(rows) / total if total else None,
        "small_sample": len(rows) < minimum_group_size,
        "dominant": bool(name not in {"unavailable", "ambiguous"} and share is not None and
                        (share >= threshold or len(rows) == total))}


def _liquidity_band(value: Any, bands: tuple[float, ...]) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "unavailable"
    for index, lower in enumerate(bands):
        if index + 1 < len(bands) and value < bands[index + 1]:
            return f"[{lower:g},{bands[index + 1]:g})"
    return f">={bands[-1]:g}"


def build_stability_evidence(*, selected_token_ids: frozenset[str], labels: tuple[Any, ...],
                             cohort: tuple[Any, ...], feature_rows: tuple[dict[str, Any], ...],
                             horizon: str, policy: StabilityPolicy) -> dict[str, Any]:
    """Describe concentration for one already-frozen discovery selection."""
    selected = [row for row in labels if row.token_id in selected_token_ids and row.horizon == horizon]
    cohort_by_id = {row.token_id: row for row in cohort}
    features = {row["token_id"]: row for row in feature_rows}
    dimensions: dict[str, list[dict[str, Any]]] = {}
    for dimension in policy.dimensions:
        groups: dict[str, list[Any]] = {}
        if dimension == "leave_one_out":
            baseline = _mean(selected)
            dimensions[dimension] = [{"excluded_token_id": row.token_id, "remaining_sample_size": len(selected) - 1,
                                      "mean_return": _mean([item for item in selected if item.token_id != row.token_id]),
                                      "baseline_mean_return": baseline} for row in sorted(selected, key=lambda x: x.token_id)]
            continue
        for label in selected:
            member = cohort_by_id.get(label.token_id)
            if dimension == "chain": key = member.chain if member else "unavailable"
            elif dimension == "era":
                anchor = datetime(1970, 1, 1)
                key = (anchor + timedelta(days=((member.t0 - anchor).days // policy.era_days) * policy.era_days)).date().isoformat() if member and member.t0 else "unavailable"
            elif dimension == "liquidity_band": key = _liquidity_band(features.get(label.token_id, {}).get("launch_liquidity_usd"), policy.liquidity_bands_usd)
            else:
                sources = sorted({str(item.get("source")) for item in (member.source_evidence if member else ())
                                  if item.get("source") and member and member.t0 and
                                  _observed_at_or_before(item, member.t0)})
                key = sources[0] if len(sources) == 1 else "ambiguous" if len(sources) > 1 else "unavailable"
            groups.setdefault(key, []).append(label)
        dimensions[dimension] = [_group_summary(key, groups[key], len(selected), policy.dominance_threshold,
                                                 policy.minimum_group_size)
                                 for key in sorted(groups)]
    groups = [item for dimension in dimensions.values() for item in dimension if "dominant" in item]
    complete = any(_valid(row) for row in selected)
    return {"version": STABILITY_VERSION, "policy": policy, "horizon": horizon,
            "selected_token_ids": sorted(selected_token_ids), "sample_size": len(selected),
            "dimensions": dimensions, "status": "available" if complete else "unavailable",
            "reason": "NO_SELECTED_OBSERVATIONS" if not selected else
            "NO_COMPLETE_OBSERVATIONS" if not complete else None,
            "dominated": any(item["dominant"] for item in groups) if complete else False}
