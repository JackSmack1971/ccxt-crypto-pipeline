from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping

from analysis.datasets.snapshot import DatasetSnapshot
from ._common import address_key, as_time, coverage_report, first, identity, numeric, payload
from .eligibility import ChainEligibility

@dataclass(frozen=True)
class CohortConfig:
    start: datetime
    end: datetime
    chains: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ("new_pool_detected", "token_mint_detected")
    primary_liquidity_usd: float = 10_000.0
    liquidity_sensitivities: tuple[float, ...] = (5_000.0, 25_000.0, 50_000.0)
    min_source_quality: bool = True
    coverage_horizon: str = "1h"
    min_coverage: float = 0.8
    chain_eligibility: Mapping[str, ChainEligibility] | None = None

    def __post_init__(self):
        if self.end < self.start: raise ValueError("invalid cohort interval")
        if self.primary_liquidity_usd != 10_000.0: raise ValueError("primary liquidity gate is fixed at $10,000")
        if tuple(self.liquidity_sensitivities) != (5_000.0, 25_000.0, 50_000.0):
            raise ValueError("liquidity sensitivity gates are fixed at $5,000/$25,000/$50,000")
        if not 0 < self.min_coverage <= 1: raise ValueError("min_coverage must be in (0, 1]")

@dataclass(frozen=True)
class CohortRow:
    token_id: str
    chain: str
    address: str
    canonical_id: str
    t0: datetime | None
    first_observed: datetime | None
    included: bool
    analysis_eligible: bool
    exclusion_reason: str | None
    liquidity_usd: float | None
    event_types: tuple[str, ...]
    source_evidence: tuple[dict[str, Any], ...]
    provenance: dict[str, Any]

def _address(event: dict[str, Any], asset: Any) -> str | None:
    body = payload(event)
    direct = first(body, "token_address", "contract_address", "mint", "token_mint", "base_token_address")
    if direct: return str(direct)
    pending = [body]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            direct = first(value, "token_address", "contract_address", "mint", "token_mint", "base_token_address")
            if direct: return str(direct)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    # Symbol text is deliberately not an identity fallback.  An unresolved
    # event is retained as an exclusion so selection effects remain visible.
    return getattr(asset, "contract_address", None)

def extract_cohort(snapshot: DatasetSnapshot, config: CohortConfig) -> tuple[CohortRow, ...]:
    assets = {a.canonical_id: a for a in snapshot.assets}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in snapshot.events:
        if event.get("event_type") not in config.event_types: continue
        when = as_time(event["timestamp"])
        if not (config.start <= when <= config.end): continue
        asset = assets.get(event.get("canonical_id"))
        if asset is None:
            key = f"unresolved:{event.get('canonical_id', '')}"
            grouped.setdefault(key, []).append(event)
            continue
        chain = str(getattr(asset, "chain_or_exchange", ""))
        if config.chains and chain not in config.chains: continue
        relationships = snapshot.relationships_at(asset.canonical_id, when)
        constituents = sorted({item["asset_canonical_id"] for item in relationships
                               if item["market_canonical_id"] == asset.canonical_id})
        if constituents:
            for token_id in constituents:
                grouped.setdefault(token_id, []).append(event)
            continue
        # A relationship observed only later is not available at this decision
        # boundary and must not cause the pool address to become a token identity.
        if any(item["market_canonical_id"] == asset.canonical_id for item in snapshot.asset_relationships):
            grouped.setdefault(f"unresolved:{asset.canonical_id}", []).append(event)
            continue
        address = _address(event, asset)
        if not address:
            grouped.setdefault(f"unresolved:{asset.canonical_id}", []).append(event)
            continue
        token_id = identity(chain, address)
        grouped.setdefault(token_id, []).append(event)
    result: list[CohortRow] = []
    for token_id, events in grouped.items():
        events = sorted(events, key=lambda e: (as_time(e["timestamp"]), str(e.get("source", "")), str(e.get("canonical_id", ""))))
        first_event = events[0]; t0 = as_time(first_event["timestamp"])
        asset = assets.get(token_id)
        chain = str(asset.chain_or_exchange) if asset else "unknown"
        address = "" if token_id.startswith("unresolved:") else (token_id.split(":", 1)[1] if ":" in token_id else "")
        evidence = tuple({"canonical_id": e["canonical_id"], "event_type": e["event_type"],
                          "timestamp": as_time(e["timestamp"]).isoformat(), "source": e.get("source"),
                          "payload": payload(e)} for e in events)
        at_t0 = [e for e in events if as_time(e["timestamp"]) <= t0]
        liquidity = next((numeric(first(payload(e), "liquidity_usd", "reserve_usd", "usd_liquidity")) for e in at_t0
                          if numeric(first(payload(e), "liquidity_usd", "reserve_usd", "usd_liquidity")) is not None), None)
        eligible = bool(asset and address and first_event.get("source")) and (not config.min_source_quality or bool(evidence))
        reason = None if eligible else "MISSING_SOURCE_PROVENANCE"
        chain_quality = config.chain_eligibility.get(chain) if config.chain_eligibility else None
        coverage = None
        if eligible and chain_quality is not None and not chain_quality.eligible:
            # A chain whose provider observation history fails the offline
            # quality gate is treated as ineligible for analysis regardless of
            # liquidity/coverage: those values were computed from the same
            # unreliable feed and cannot be trusted to justify inclusion.
            analysis = False
            reason = "CHAIN_PROVIDER_QUALITY_INELIGIBLE"
        else:
            analysis = eligible and liquidity is not None and liquidity >= config.primary_liquidity_usd
            if eligible and liquidity is None: reason = "LIQUIDITY_UNAVAILABLE"
            elif eligible and liquidity is not None and liquidity < config.primary_liquidity_usd: reason = "BELOW_LIQUIDITY_GATE"
            if eligible and analysis and asset:
                horizon_seconds = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}.get(config.coverage_horizon)
                if horizon_seconds is None: raise ValueError("unsupported coverage horizon")
                from datetime import timedelta
                coverage = coverage_report(snapshot.bars_for(asset.canonical_id), t0,
                                           t0 + timedelta(seconds=horizon_seconds), snapshot.policy.timeframe)
                if not coverage["passes"]:
                    analysis = False
                    reason = "INSUFFICIENT_COVERAGE"
        first_seen = asset.first_seen if asset else t0
        result.append(CohortRow(token_id, chain, address, token_id if asset else first_event.get("canonical_id", ""), t0, first_seen, eligible, analysis,
                                reason, liquidity, tuple(sorted({e["event_type"] for e in events})), evidence,
                                {"dataset_identity": snapshot.dataset_identity, "cohort_config": asdict(config),
                                 "market_canonical_ids": tuple(sorted({e["canonical_id"] for e in events
                                                                       if e["canonical_id"] != token_id})),
                                 "coverage": coverage,
                                 "chain_eligibility": ({"eligible": chain_quality.eligible, "reason": chain_quality.reason}
                                                       if chain_quality is not None else None)}))
    return tuple(sorted(result, key=lambda r: (r.t0 or datetime.max, r.token_id)))
