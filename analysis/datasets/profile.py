"""Deterministic, explicit quality evidence for one read-only dataset snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from .snapshot import DatasetSnapshot


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, default=str, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _duration(value: str) -> timedelta:
    match = re.fullmatch(r"(\d+)([mhd])", value)
    if not match:
        raise ValueError(f"unsupported profile timeframe: {value}")
    amount, unit = int(match.group(1)), match.group(2)
    return timedelta(**{"minutes" if unit == "m" else "hours" if unit == "h" else "days": amount})


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _status(status: str, **evidence: Any) -> dict[str, Any]:
    return {"status": status, **evidence}


def build_dataset_profile(
    dataset: DatasetSnapshot,
    *,
    label_horizons: tuple[str, ...] = (),
    question_fitness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a content-addressed quality profile without contacting providers.

    Evidence that cannot be derived from a snapshot is retained as an explicit
    ``unavailable`` state.  The profile is descriptive; it does not collapse
    correctness, completeness, representativeness, or question fitness into a
    single score.
    """
    policy = dataset.policy
    by_series: dict[tuple[str, str, str], list[datetime]] = {}
    for bar in dataset.bars:
        by_series.setdefault((bar.canonical_id, bar.source, bar.timeframe), []).append(bar.timestamp)

    coverage: list[dict[str, Any]] = []
    for (asset_id, source, timeframe), timestamps in sorted(by_series.items()):
        ordered = sorted(timestamps)
        interval = _duration(timeframe)
        gaps = [int((right - left) / interval) - 1 for left, right in zip(ordered, ordered[1:])]
        expected_start = policy.start or ordered[0]
        expected_end = policy.end or ordered[-1]
        expected = max(0, int((expected_end - expected_start) / interval) + 1)
        coverage.append({
            "asset_id": asset_id,
            "source": source,
            "timeframe": timeframe,
            "observed": len(ordered),
            "expected": expected,
            "missing": max(0, expected - len(ordered)) if policy.start or policy.end else None,
            "first_observed": _iso(ordered[0]),
            "last_observed": _iso(ordered[-1]),
            "max_internal_gap_periods": max(gaps, default=0),
        })

    event_times: dict[str, list[datetime]] = {}
    for event in dataset.events:
        event_type = str(event.get("event_type", "")).lower()
        if any(term in event_type for term in ("launch", "pool", "discover")):
            event_times.setdefault(str(event["canonical_id"]), []).append(event["timestamp"])
    launch_latency = []
    for asset in dataset.assets:
        launches = event_times.get(asset.canonical_id)
        if launches:
            launch_latency.append({
                "asset_id": asset.canonical_id,
                "first_seen": _iso(asset.first_seen),
                "first_launch_event": _iso(min(launches)),
                "latency_seconds": (asset.first_seen - min(launches)).total_seconds(),
            })

    quote_gaps = []
    for asset_id, quote_id in sorted(dataset.quote_assets.items()):
        normalized = quote_id.lower().replace("-", ":").split(":")[-1]
        stable = normalized in {"usd", "usdt", "usdc", "dai", "busd"} or normalized.endswith("/usd")
        has_conversion = bool(dataset.reference_series_at(quote_id, datetime.max))
        if not stable and not has_conversion:
            quote_gaps.append({"asset_id": asset_id, "quote_asset": quote_id, "status": "unavailable"})

    horizon_censoring: dict[str, Any]
    if not label_horizons:
        horizon_censoring = _status("unavailable", reason="no label horizons were declared")
    elif policy.end is None:
        horizon_censoring = _status("unavailable", reason="dataset policy has no end boundary")
    else:
        horizon_censoring = _status("observed", horizons={
            horizon: sum(1 for bar in dataset.bars if bar.timestamp + _duration(horizon) > policy.end)
            for horizon in sorted(label_horizons)
        })

    profile: dict[str, Any] = {
        "profile_version": "phase8r-dataset-profile-v1",
        "dataset_identity": dataset.dataset_identity,
        "query_policy": {
            "version": policy.query_policy_version,
            "timeframe": policy.timeframe,
            "start": _iso(policy.start),
            "end": _iso(policy.end),
            "sources": list(policy.sources),
            "asset_ids": list(policy.asset_ids),
        },
        "counts": {
            "assets": len(dataset.assets),
            "bars": len(dataset.bars),
            "metadata_observations": len(dataset.metadata),
            "events": len(dataset.events),
            "relationships": len(dataset.asset_relationships),
            "reference_series_observations": len(dataset.reference_series),
        },
        "coverage": coverage,
        "launch_detection": launch_latency or _status("unavailable", reason="no launch-like events in snapshot"),
        "liquidity": _status("unavailable", reason="snapshot bars do not carry liquidity observations"),
        "missingness": {
            "series": coverage,
            "gaps": [{"asset_id": row["asset_id"], "source": row["source"],
                      "max_internal_gap_periods": row["max_internal_gap_periods"]}
                     for row in coverage if row["max_internal_gap_periods"]],
        },
        "source_disagreement": _status("unavailable", reason="snapshot requires one unambiguous bar source per series"),
        "censoring": {"label_horizons": horizon_censoring, "quote_conversion_gaps": quote_gaps},
        "identity": _status("verified", duplicate_assets=0, ambiguous_assets=0),
        "unsupported_or_unavailable": {
            "observation_capabilities": _status("unavailable", reason="capabilities are not part of the snapshot contract"),
            "dead_or_delisted_retention": _status("unavailable", reason="asset lifecycle status is not declared"),
        },
        "correctness": _status("verified", basis="DatasetSnapshot validation"),
        "completeness": _status("observed", bounded=bool(policy.start and policy.end)),
        "representativeness": _status("unavailable", reason="requires an external declared sampling frame"),
        "question_fitness": dict(question_fitness) if question_fitness is not None else _status(
            "unavailable", reason="no research question was supplied"),
    }
    profile["profile_identity"] = hashlib.sha256(_canonical(profile)).hexdigest()
    return profile


def write_dataset_profile(profile: Mapping[str, Any], output_dir: str | Path) -> Path:
    """Write or verify one immutable JSON profile artifact."""
    profile = dict(profile)
    profile_id = profile.get("profile_identity")
    if not isinstance(profile_id, str) or profile_id != hashlib.sha256(
        _canonical({key: value for key, value in profile.items() if key != "profile_identity"})
    ).hexdigest():
        raise ValueError("dataset profile identity mismatch")
    target = Path(output_dir) / profile_id
    target.mkdir(parents=True, exist_ok=True)
    path = target / "profile.json"
    content = _canonical(profile)
    if path.exists() and path.read_bytes() != content:
        raise FileExistsError(f"immutable dataset profile differs: {path}")
    if not path.exists():
        path.write_bytes(content)
    return path


def verify_dataset_profile(profile: Mapping[str, Any], dataset_identity: str) -> str:
    """Return the exact profile identity when it is bound to a dataset identity."""
    if profile.get("dataset_identity") != dataset_identity:
        raise ValueError("dataset profile is bound to a different dataset identity")
    profile_id = profile.get("profile_identity")
    expected = hashlib.sha256(_canonical({key: value for key, value in profile.items()
                                          if key != "profile_identity"})).hexdigest()
    if profile_id != expected:
        raise ValueError("dataset profile identity mismatch")
    return profile_id
