from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from analysis.datasets.snapshot import DatasetSnapshot
from ._common import as_time, coverage_report, numeric

@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    source_columns: tuple[str, ...]
    effective_timestamp: str
    lookback: timedelta
    missing_value_policy: str = "unknown"
    allowed_horizons: tuple[str, ...] = ()
    compute: Callable[[Any, tuple[Any, ...]], Any] | None = None
    source_timestamp: str | None = None
    version: str = "v1"

    def __post_init__(self):
        if self.missing_value_policy not in {"unknown", "zero", "reject"}: raise ValueError("unsupported missing-value policy")
        if self.lookback.total_seconds() < 0: raise ValueError("lookback must be non-negative")
        if not self.version.strip(): raise ValueError("feature definition requires a version")


def feature_definition_id(definition: FeatureDefinition) -> str:
    """Content-addressed identity for a resolved feature definition.

    Covers every declared, hashable field except ``compute``: the executable
    behavior behind a (name, version) pair is governed by catalog discipline
    in ``analysis/alpha/registry.py`` (a version bump is required whenever a
    catalog entry's compute behavior changes), the same pattern already used
    for other Phase 3 config objects that version behavior without hashing
    Python code directly.
    """
    payload = {
        "name": definition.name, "version": definition.version,
        "source_columns": definition.source_columns,
        "effective_timestamp": definition.effective_timestamp,
        "lookback_seconds": definition.lookback.total_seconds(),
        "missing_value_policy": definition.missing_value_policy,
        "allowed_horizons": definition.allowed_horizons,
        "source_timestamp": definition.source_timestamp,
    }
    return hashlib.sha256((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()[:24]

class FeatureRegistry:
    def __init__(self): self._items: dict[str, FeatureDefinition] = {}
    def register(self, definition: FeatureDefinition) -> None:
        if definition.name in self._items: raise ValueError(f"duplicate feature: {definition.name}")
        self._items[definition.name] = definition
    def get(self, name: str) -> FeatureDefinition: return self._items[name]
    def definitions(self): return tuple(self._items[name] for name in sorted(self._items))

def compute_features(snapshot: DatasetSnapshot, cohort: tuple[Any, ...], registry: FeatureRegistry,
                     *, decision_time: str = "t0") -> tuple[dict[str, Any], ...]:
    rows = []
    for member in cohort:
        point = as_time(getattr(member, decision_time))
        values: dict[str, Any] = {"token_id": member.token_id, "decision_time": point.isoformat(),
                                  "provenance": {"dataset_identity": snapshot.dataset_identity, "token_id": member.token_id}}
        for definition in registry.definitions():
            if definition.effective_timestamp not in {"t0", "decision_time"}: raise ValueError("unsupported feature effective timestamp")
            if definition.source_timestamp is not None and as_time(definition.source_timestamp) > point:
                raise ValueError(f"future feature observation: {definition.name}")
            bars = tuple(b for b in snapshot.bars_for(member.canonical_id)
                         if point - definition.lookback <= b.timestamp <= point)
            if any(b.timestamp > point for b in bars): raise ValueError(f"future feature observation: {definition.name}")
            value = definition.compute(member, bars) if definition.compute else None
            if value is None and definition.missing_value_policy == "zero": value = 0.0
            if value is None and definition.missing_value_policy == "reject": values.setdefault("rejected_features", []).append(definition.name)
            values[definition.name] = value
            interval_start = point - definition.lookback
            values.setdefault("coverage", {})[definition.name] = coverage_report(bars, interval_start, point, snapshot.policy.timeframe)
            values.setdefault("feature_provenance", {})[definition.name] = {
                "source_columns": definition.source_columns, "effective_timestamp": point.isoformat(),
                "lookback_seconds": definition.lookback.total_seconds(), "missing_value_policy": definition.missing_value_policy,
                "allowed_horizons": definition.allowed_horizons, "observation_count": len(bars),
                "coverage": values["coverage"][definition.name],
                "feature_version": definition.version, "feature_definition_id": feature_definition_id(definition),
            }
            if definition.source_timestamp is not None:
                values["feature_provenance"][definition.name]["source_timestamp"] = as_time(definition.source_timestamp).isoformat()
            if definition.effective_timestamp in {"t0", "decision_time"}:
                values["feature_provenance"][definition.name]["latest_allowed_timestamp"] = point.isoformat()
        rows.append(values)
    return tuple(rows)

def launch_liquidity_feature():
    return FeatureDefinition("launch_liquidity_usd", ("event.payload_json.reserve_usd",), "t0", timedelta(0), compute=lambda member, bars: member.liquidity_usd)

def close_return_feature(lookback: timedelta, name: str = "lookback_return"):
    def compute(_member, bars):
        valid = [numeric(b.close) for b in bars if numeric(b.close) is not None and b.close > 0]
        return None if len(valid) < 2 else __import__("math").log(valid[-1] / valid[0])
    return FeatureDefinition(name, ("ohlcv.close",), "t0", lookback, compute=compute)
