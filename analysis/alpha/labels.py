from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from analysis.datasets.snapshot import DatasetSnapshot
from ._common import as_time, coverage_report

HORIZONS = {"1h": (timedelta(hours=1), timedelta(minutes=5)), "6h": (timedelta(hours=6), timedelta(minutes=15)),
            "24h": (timedelta(days=1), timedelta(minutes=30)), "7d": (timedelta(days=7), timedelta(hours=2))}

@dataclass(frozen=True)
class LabelDefinition:
    name: str
    horizon: str
    quote_currency: str = "USD"
    censoring_policy: str = "economic_failure/data_censored/right_censored"
    unavailable_treatment: str = "explicit_censoring"

    def __post_init__(self):
        if self.horizon not in HORIZONS or self.quote_currency != "USD": raise ValueError("labels require canonical USD horizon")

@dataclass(frozen=True)
class LabelRow:
    token_id: str
    horizon: str
    value: float | None
    status: str
    start_time: str
    end_time: str
    start_price_usd: float | None
    end_price_usd: float | None
    provenance: dict[str, Any]

def normalize_usd_price(raw_price: float, *, quote_asset: str = "USD", conversion_rate: float | None = 1.0,
                        conversion_source: str = "native_usd") -> tuple[float, dict[str, Any]]:
    """Normalize a locally persisted quote to USD; never assume a missing conversion."""
    if conversion_rate is None or conversion_rate <= 0 or not math.isfinite(conversion_rate):
        raise ValueError("quote-to-USD conversion is unavailable")
    price = float(raw_price) * conversion_rate
    return price, {"raw_quote": quote_asset, "conversion_rate": conversion_rate,
                   "conversion_source": conversion_source, "quote_currency": "USD"}

def generate_labels(snapshot: DatasetSnapshot, cohort: tuple[Any, ...], definition: LabelDefinition, *,
                    price_normalizer=None) -> tuple[LabelRow, ...]:
    duration, tolerance = HORIZONS[definition.horizon]; result = []
    for member in cohort:
        start = as_time(member.t0); target = start + duration
        bars = tuple(snapshot.bars_for(member.canonical_id))
        coverage = coverage_report(bars, start, target, snapshot.policy.timeframe)
        def choose(point):
            candidates = [b for b in bars if abs(b.timestamp - point) <= tolerance and b.close > 0 and b.halted is False]
            return min(candidates, key=lambda b: (abs(b.timestamp - point), b.timestamp)) if candidates else None
        begin = choose(start); end = choose(target)
        status = "COMPLETE" if begin and end and coverage["passes"] else ("RIGHT_CENSORED" if snapshot.policy.end and as_time(snapshot.policy.end) < target else "DATA_CENSORED")
        normalizer = price_normalizer or (lambda bar: normalize_usd_price(bar.close))
        try:
            begin_price, begin_provenance = normalizer(begin) if begin else (None, {})
            end_price, end_provenance = normalizer(end) if end else (None, {})
        except ValueError:
            begin_price, end_price = None, None
            begin_provenance, end_provenance = {}, {"conversion_unavailable": True}
            status = "DATA_CENSORED"
        value = math.log(end_price / begin_price) if begin_price and end_price else None
        if not coverage["passes"]: value = None
        if not end and any(b.halted and b.timestamp >= (begin.timestamp if begin else start) for b in bars): status = "ECONOMIC_FAILURE"
        result.append(LabelRow(member.token_id, definition.horizon, value, status, start.isoformat(), target.isoformat(),
                               begin_price, end_price,
                               {"dataset_identity": snapshot.dataset_identity, **begin_provenance, "end_conversion": end_provenance,
                                "coverage": coverage,
                                "tolerance_seconds": tolerance.total_seconds()}))
    return tuple(result)
