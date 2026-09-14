from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from analysis.datasets.snapshot import DatasetSnapshot
from ._common import as_time, coverage_report

HORIZONS = {"1h": (timedelta(hours=1), timedelta(minutes=5)), "6h": (timedelta(hours=6), timedelta(minutes=15)),
            "24h": (timedelta(days=1), timedelta(minutes=30)), "7d": (timedelta(days=7), timedelta(hours=2))}


@dataclass(frozen=True)
class ConversionPolicy:
    """Versioned rules for converting locally persisted quote prices to USD."""

    version: str = "phase3-quote-usd-v1"
    approved_stablecoins: tuple[str, ...] = ()
    maximum_age: timedelta | None = None

    def __post_init__(self):
        normalized = tuple(item.strip().upper() for item in self.approved_stablecoins)
        if not self.version.strip() or any(not item for item in normalized):
            raise ValueError("conversion policy requires a version and valid stablecoin identities")
        if len(set(normalized)) != len(normalized):
            raise ValueError("conversion policy contains duplicate stablecoin identities")
        if self.maximum_age is not None and self.maximum_age < timedelta(0):
            raise ValueError("conversion maximum age cannot be negative")
        object.__setattr__(self, "approved_stablecoins", normalized)


@dataclass(frozen=True)
class ConversionObservation:
    quote_asset: str
    timestamp: datetime
    usd_rate: float
    source: str

    def __post_init__(self):
        if not self.quote_asset.strip() or not self.source.strip():
            raise ValueError("conversion observation requires quote identity and source")
        if self.usd_rate <= 0 or not math.isfinite(self.usd_rate):
            raise ValueError("conversion observation rate must be positive and finite")

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


def _reference_series_observations(quote: str, point: datetime,
                                   snapshot: DatasetSnapshot | None) -> tuple[ConversionObservation, ...]:
    """Read persisted point-in-time reference series rows as reusable conversion evidence."""
    if snapshot is None:
        return ()
    rows = snapshot.reference_series_at(f"{quote}/USD", point)
    return tuple(ConversionObservation(quote, row["observed_at"], row["value"], row["source"]) for row in rows)


def _convert_at(raw_price: float, quote_asset: str, point: datetime,
                observations: tuple[ConversionObservation, ...], policy: ConversionPolicy,
                snapshot: DatasetSnapshot | None = None) -> tuple[float, dict[str, Any]]:
    quote = quote_asset.strip().upper()
    if not quote:
        raise ValueError("quote asset identity is unavailable")
    if quote == "USD":
        rate, source, observed = 1.0, "native_usd", point
    elif quote in policy.approved_stablecoins:
        rate, source, observed = 1.0, "approved_stablecoin_parity", point
    else:
        candidates = observations + _reference_series_observations(quote, point, snapshot)
        eligible = [item for item in candidates
                    if item.quote_asset.strip().upper() == quote and as_time(item.timestamp) <= point]
        if not eligible:
            raise ValueError(f"no temporally valid {quote}/USD conversion")
        latest_time = max(as_time(item.timestamp) for item in eligible)
        latest = [item for item in eligible if as_time(item.timestamp) == latest_time]
        if len(latest) != 1:
            raise ValueError(f"ambiguous {quote}/USD conversion sources")
        selected = latest[0]
        observed = as_time(selected.timestamp)
        if policy.maximum_age is not None and point - observed > policy.maximum_age:
            raise ValueError(f"no temporally valid {quote}/USD conversion")
        rate, source = selected.usd_rate, selected.source
    return float(raw_price) * rate, {
        "quote_asset": quote, "conversion_rate": rate, "conversion_source": source,
        "conversion_time": observed.isoformat(), "conversion_policy": policy.version,
    }

def generate_labels(snapshot: DatasetSnapshot, cohort: tuple[Any, ...], definition: LabelDefinition, *,
                    price_normalizer=None, quote_assets: dict[str, str] | None = None,
                    conversion_observations: tuple[ConversionObservation, ...] = (),
                    conversion_policy: ConversionPolicy | None = None) -> tuple[LabelRow, ...]:
    duration, tolerance = HORIZONS[definition.horizon]; result = []
    quote_assets = quote_assets or {}
    conversion_policy = conversion_policy or ConversionPolicy()
    for member in cohort:
        start = as_time(member.t0); target = start + duration
        bars = tuple(snapshot.bars_for(member.canonical_id))
        coverage = coverage_report(bars, start, target, snapshot.policy.timeframe)
        def choose(point):
            candidates = [b for b in bars if abs(b.timestamp - point) <= tolerance and b.close > 0 and b.halted is False]
            return min(candidates, key=lambda b: (abs(b.timestamp - point), b.timestamp)) if candidates else None
        begin = choose(start); end = choose(target)
        status = "COMPLETE" if begin and end and coverage["passes"] else ("RIGHT_CENSORED" if snapshot.policy.end and as_time(snapshot.policy.end) < target else "DATA_CENSORED")
        quote_asset = quote_assets.get(member.canonical_id, "USD")
        normalizer = price_normalizer or (lambda bar: _convert_at(
            bar.close, quote_asset, bar.timestamp, conversion_observations, conversion_policy, snapshot))
        try:
            begin_price, begin_provenance = normalizer(begin) if begin else (None, {})
            end_price, end_provenance = normalizer(end) if end else (None, {})
            conversion_error = None
        except ValueError as error:
            begin_price, end_price = None, None
            begin_provenance, end_provenance = {}, {}
            conversion_error = str(error)
            status = "DATA_CENSORED"
        value = math.log(end_price / begin_price) if begin_price and end_price else None
        if not coverage["passes"]: value = None
        if not end and any(b.halted and b.timestamp >= (begin.timestamp if begin else start) for b in bars): status = "ECONOMIC_FAILURE"
        result.append(LabelRow(member.token_id, definition.horizon, value, status, start.isoformat(), target.isoformat(),
                               begin_price, end_price,
                               {"dataset_identity": snapshot.dataset_identity, "raw_quote": quote_asset,
                                "quote_currency": definition.quote_currency,
                                "conversion_policy": conversion_policy.version,
                                "start_conversion": begin_provenance, "end_conversion": end_provenance,
                                **({"conversion_unavailable": conversion_error} if conversion_error else {}),
                                "coverage": coverage,
                                "tolerance_seconds": tolerance.total_seconds()}))
    return tuple(result)
