"""Read-only, deterministic point-in-time dataset views.

This module deliberately imports only the repository's local storage reader.  It
does not know how to contact a provider and it never writes to the canonical
store.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb


def _time(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        if value is None:
            raise ValueError("timestamp is unavailable")
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return parsed.replace(tzinfo=None)


@dataclass(frozen=True)
class Asset:
    canonical_id: str
    source_type: str
    chain_or_exchange: str
    symbol_or_contract: str
    first_seen: datetime
    contract_address: str | None


@dataclass(frozen=True)
class Bar:
    canonical_id: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str
    source: str

    @property
    def halted(self) -> bool:
        return self.volume == 0 and self.open == self.high == self.low == self.close


@dataclass(frozen=True)
class Metadata:
    canonical_id: str
    holder_count: int | None
    lp_locked: bool | None
    contract_verified: bool | None
    deployer_address: str | None
    risk_flags_json: str | None
    last_updated: datetime


@dataclass(frozen=True)
class DatasetPolicy:
    query_policy_version: str = "phase2-pit-v1"
    timeframe: str = "1d"
    start: datetime | None = None
    end: datetime | None = None
    sources: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()

    def allows(self, bar: Bar) -> bool:
        return (
            bar.timeframe == self.timeframe
            and (not self.sources or bar.source in self.sources)
            and (not self.asset_ids or bar.canonical_id in self.asset_ids)
            and (self.start is None or bar.timestamp >= self.start)
            and (self.end is None or bar.timestamp <= self.end)
        )


class DatasetSnapshot:
    """Materialized immutable inputs used by one research run."""

    def __init__(self, assets: tuple[Asset, ...], bars: tuple[Bar, ...],
                 metadata: tuple[Metadata, ...], events: tuple[dict[str, Any], ...],
                 lineage: tuple[dict[str, Any], ...], policy: DatasetPolicy,
                 dataset_identity: str):
        self.assets = tuple(sorted(assets, key=lambda item: item.canonical_id))
        self.bars = tuple(sorted((bar for bar in bars if policy.allows(bar)),
                                 key=lambda item: (item.timestamp, item.canonical_id,
                                                   item.timeframe, item.source)))
        bar_keys = [(item.canonical_id, item.timestamp, item.timeframe, item.source) for item in self.bars]
        if len(set(bar_keys)) != len(bar_keys):
            raise ValueError("duplicate bar identity")
        selected_keys = [(item.canonical_id, item.timestamp, item.timeframe) for item in self.bars]
        if len(set(selected_keys)) != len(selected_keys):
            raise ValueError("ambiguous bar source: select one source in DatasetPolicy.sources")
        self.metadata = tuple(sorted(metadata, key=lambda item: (item.canonical_id, item.last_updated)))
        metadata_keys = [(item.canonical_id, item.last_updated) for item in self.metadata]
        if len(set(metadata_keys)) != len(metadata_keys):
            raise ValueError("duplicate metadata observation")
        self.events = tuple(sorted(events, key=lambda item: (_time(item["timestamp"]),
                                                               str(item.get("canonical_id", "")),
                                                               str(item.get("event_type", "")),
                                                               str(item.get("source", "")))))
        self.lineage = tuple(sorted(lineage, key=lambda item: (str(item.get("dex_canonical_id", "")),
                                                               str(item.get("cex_canonical_id", "")),
                                                               _time(item["linked_at"]))))
        self.policy = policy
        self.dataset_identity = dataset_identity
        self._asset_ids = {item.canonical_id for item in assets}
        self._metadata: dict[str, tuple[Metadata, ...]] = {}
        for item in self.metadata:
            self._metadata.setdefault(item.canonical_id, tuple())
            self._metadata[item.canonical_id] += (item,)
        self._bars_by_asset: dict[str, tuple[Bar, ...]] = {}
        for bar in self.bars:
            self._bars_by_asset.setdefault(bar.canonical_id, tuple())
            self._bars_by_asset[bar.canonical_id] += (bar,)

    @classmethod
    def from_duckdb(cls, db_path: str | Path, policy: DatasetPolicy | None = None,
                    parquet_dir: str | Path | None = None) -> "DatasetSnapshot":
        policy = policy or DatasetPolicy()
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()}
            required = {"assets", "ohlcv", "metadata", "events", "lineage"}
            missing = sorted(required - tables)
            if missing:
                raise ValueError(f"dataset is missing required tables: {', '.join(missing)}")
            asset_rows = conn.execute(
                "SELECT canonical_id, source_type, chain_or_exchange, symbol_or_contract, first_seen, contract_address "
                "FROM assets ORDER BY canonical_id"
            ).fetchall()
            assets = tuple(Asset(row[0], row[1], row[2], row[3], _time(row[4]), row[5]) for row in asset_rows)
            if len({asset.canonical_id for asset in assets}) != len(assets):
                raise ValueError("ambiguous asset identity: canonical_id is not unique")
            if parquet_dir is None:
                rows = conn.execute(
                    "SELECT canonical_id, timestamp, open, high, low, close, volume, timeframe, source "
                    "FROM ohlcv ORDER BY timestamp, canonical_id, timeframe, source"
                ).fetchall()
            else:
                paths = sorted(Path(parquet_dir).glob("source=*/date=*/*.parquet"))
                if not paths:
                    raise ValueError(f"parquet dataset contains no partitions: {parquet_dir}")
                rows = conn.execute(
                    "SELECT canonical_id, timestamp, open, high, low, close, volume, timeframe, source "
                    "FROM read_parquet(?) ORDER BY timestamp, canonical_id, timeframe, source",
                    [[str(path) for path in paths]],
                ).fetchall()
            bars = []
            seen = set()
            for row in rows:
                bar = Bar(row[0], _time(row[1]), float(row[2]), float(row[3]), float(row[4]),
                          float(row[5]), float(row[6]), row[7], row[8])
                if not all(math.isfinite(value) for value in (bar.open, bar.high, bar.low, bar.close, bar.volume)):
                    raise ValueError(f"bar contains a non-finite price or volume: {bar.canonical_id} at {bar.timestamp.isoformat()}")
                key = (bar.canonical_id, bar.timestamp, bar.timeframe, bar.source)
                if key in seen:
                    raise ValueError(f"duplicate bar identity: {key}")
                seen.add(key)
                if bar.canonical_id not in {asset.canonical_id for asset in assets}:
                    raise ValueError(f"bar references unknown canonical_id: {bar.canonical_id}")
                if policy.allows(bar):
                    bars.append(bar)
            metadata = tuple(Metadata(*row[:6], _time(row[6])) for row in conn.execute(
                "SELECT canonical_id, holder_count, lp_locked, contract_verified, deployer_address, "
                "risk_flags_json, last_updated FROM metadata ORDER BY canonical_id, last_updated"
            ).fetchall())
            events = tuple(dict(zip(("canonical_id", "event_type", "timestamp", "payload_json", "source"), row))
                           for row in conn.execute("SELECT canonical_id, event_type, timestamp, payload_json, source "
                                                   "FROM events ORDER BY timestamp, canonical_id, event_type, source").fetchall())
            for event in events:
                event["timestamp"] = _time(event["timestamp"])
            lineage = tuple(dict(zip(("dex_canonical_id", "cex_canonical_id", "linked_at"), row))
                            for row in conn.execute("SELECT dex_canonical_id, cex_canonical_id, linked_at FROM lineage "
                                                    "ORDER BY dex_canonical_id, cex_canonical_id, linked_at").fetchall())
            for link in lineage:
                link["linked_at"] = _time(link["linked_at"])
            asset_ids = {asset.canonical_id for asset in assets}
            unknown_metadata = sorted(item.canonical_id for item in metadata if item.canonical_id not in asset_ids)
            unknown_events = sorted(item["canonical_id"] for item in events if item["canonical_id"] not in asset_ids)
            unknown_lineage = sorted({item[key] for item in lineage for key in ("dex_canonical_id", "cex_canonical_id")
                                      if item[key] not in asset_ids})
            if unknown_metadata or unknown_events or unknown_lineage:
                raise ValueError("dataset references unknown canonical asset identities: " +
                                 ", ".join(unknown_metadata + unknown_events + unknown_lineage))
        finally:
            conn.close()
        payload = {"assets": [asdict(x) for x in assets], "bars": [asdict(x) for x in bars],
                   "metadata": [asdict(x) for x in metadata], "events": list(events), "lineage": list(lineage),
                   "policy": asdict(policy)}
        identity = hashlib.sha256(json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return cls(assets, tuple(bars), metadata, events, lineage, policy, identity)

    def bars_for(self, canonical_id: str) -> tuple[Bar, ...]:
        if canonical_id not in self._asset_ids:
            raise ValueError(f"unknown canonical asset identity: {canonical_id}")
        return self._bars_by_asset.get(canonical_id, ())

    def metadata_at(self, canonical_id: str, decision_time: datetime) -> Metadata | None:
        observations = self._metadata.get(canonical_id, ())
        available = [item for item in observations if item.last_updated <= _time(decision_time)]
        return max(available, key=lambda item: item.last_updated) if available else None

    def lineage_at(self, canonical_id: str, decision_time: datetime) -> tuple[dict[str, Any], ...]:
        """Return only lineage known at the point in time being evaluated."""
        point = _time(decision_time)
        return tuple(link for link in self.lineage
                     if (link.get("dex_canonical_id") == canonical_id or
                         link.get("cex_canonical_id") == canonical_id)
                     and _time(link["linked_at"]) <= point)

    def events_at(self, canonical_id: str, decision_time: datetime) -> tuple[dict[str, Any], ...]:
        point = _time(decision_time)
        return tuple(event for event in self.events if event["canonical_id"] == canonical_id and _time(event["timestamp"]) <= point)

    def all_bars(self) -> tuple[Bar, ...]:
        return self.bars
