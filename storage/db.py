"""Small, provider-agnostic access layer for the canonical local store."""

from __future__ import annotations

import json
import re
import uuid
import os
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .schema import SCHEMA_VERSION, initialize

_OHLCV_COLUMNS = (
    "canonical_id", "timestamp", "open", "high", "low", "close", "volume",
    "timeframe", "source",
)
_SAFE_PARTITION_VALUE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_SECRET_IN_ERROR = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+|api[_-]?key|credential|password|secret|token|rpc[_-]?url)\s*[:=]?\s*[^\s,;]+"
)
_URL_CREDENTIAL = re.compile(r"(?i)(://)[^/\s:@]+:[^/\s@]+@")


def safe_error_message(error: Exception, limit: int = 500) -> str:
    """Persist useful failure context without copying conventional credentials."""
    message = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", str(error))
    return _SECRET_IN_ERROR.sub(r"\1[REDACTED]", message)[:limit]


def connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Open a database and ensure the canonical schema exists."""
    connection = duckdb.connect(str(db_path))
    initialize(connection)
    return connection


def init_db(db_path: str | Path) -> None:
    """Initialize a database without requiring callers to manage a connection."""
    connection = connect(db_path)
    connection.close()


def _connection(db_path: str | Path | None, connection: duckdb.DuckDBPyConnection | None):
    if connection is not None:
        return connection, False
    if db_path is None:
        raise ValueError("db_path or connection is required")
    return connect(db_path), True


def _finish(connection: duckdb.DuckDBPyConnection, owned: bool) -> None:
    if owned:
        connection.close()


def upsert_asset(asset: Mapping[str, Any], db_path: str | Path | None = None, *, connection=None) -> None:
    conn, owned = _connection(db_path, connection)
    try:
        conn.execute(
            """INSERT INTO assets
            (canonical_id, source_type, chain_or_exchange, symbol_or_contract, first_seen, contract_address)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (canonical_id) DO UPDATE SET
                source_type = excluded.source_type,
                chain_or_exchange = excluded.chain_or_exchange,
                symbol_or_contract = excluded.symbol_or_contract,
                first_seen = LEAST(assets.first_seen, excluded.first_seen),
                contract_address = COALESCE(excluded.contract_address, assets.contract_address)""",
            [asset["canonical_id"], asset["source_type"], asset["chain_or_exchange"],
             asset["symbol_or_contract"], asset["first_seen"], asset.get("contract_address")],
        )
    finally:
        _finish(conn, owned)


def insert_ohlcv_batch(rows: Iterable[Mapping[str, Any]], db_path: str | Path | None = None, *,
                       parquet_dir: str | Path | None = None, connection=None) -> int:
    rows = [dict(row) for row in rows]
    if not rows:
        return 0
    conn, owned = _connection(db_path, connection)
    staged = []
    committed = False
    try:
        values = [[row[column] for column in _OHLCV_COLUMNS] for row in rows]
        conn.execute("BEGIN TRANSACTION")
        conn.executemany(
            """INSERT INTO ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (canonical_id, timestamp, timeframe, source) DO UPDATE SET
                open = excluded.open, high = excluded.high, low = excluded.low,
                close = excluded.close, volume = excluded.volume, source = excluded.source""",
            values,
        )
        if parquet_dir is None and db_path is not None:
            parquet_dir = Path(db_path).parent / "parquet"
        if parquet_dir is not None:
            staged = _write_ohlcv_partitions(conn, rows, Path(parquet_dir))
        conn.execute("COMMIT")
        committed = True
        for temporary, final in staged:
            os.replace(temporary, final)
        return len(rows)
    except Exception:
        if not committed:
            conn.execute("ROLLBACK")
        for temporary, _final in staged:
            Path(temporary).unlink(missing_ok=True)
        raise
    finally:
        _finish(conn, owned)


def _write_ohlcv_partitions(conn, rows: list[Mapping[str, Any]], root: Path) -> list[tuple[Path, Path]]:
    partitions = {(row["source"], _as_date(row["timestamp"])) for row in rows}
    staged = []
    for source, partition_date in partitions:
        if not _SAFE_PARTITION_VALUE.fullmatch(str(source)):
            raise ValueError("source must contain only safe partition characters")
        result = conn.execute(
            """SELECT canonical_id, timestamp, open, high, low, close, volume, timeframe, source
            FROM ohlcv WHERE source = ? AND CAST(timestamp AS DATE) = ?
            ORDER BY canonical_id, timestamp, timeframe""", [source, partition_date]
        ).fetchall()
        table = pa.Table.from_pylist([dict(zip(_OHLCV_COLUMNS, row)) for row in result])
        partition = root / f"source={source}" / f"date={partition_date.isoformat()}"
        partition.mkdir(parents=True, exist_ok=True)
        final = partition / "part-00000.parquet"
        temporary = partition / f".{final.name}.{uuid.uuid4().hex}.tmp"
        pq.write_table(table, temporary)
        staged.append((temporary, final))
    return staged


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def insert_event(event: Mapping[str, Any], db_path: str | Path | None = None, *, connection=None) -> None:
    conn, owned = _connection(db_path, connection)
    try:
        payload = event["payload_json"]
        if not isinstance(payload, str):
            payload = json.dumps(payload, default=str, sort_keys=True)
        conn.execute(
            """INSERT INTO events
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM events
                WHERE canonical_id = ? AND event_type = ? AND timestamp = ? AND source = ?
            )""",
            [event["canonical_id"], event["event_type"], event["timestamp"], payload,
             event["source"], event["canonical_id"], event["event_type"], event["timestamp"], event["source"]],
        )
    finally:
        _finish(conn, owned)


def upsert_asset_relationship(relationship: Mapping[str, Any], db_path: str | Path | None = None, *,
                              connection=None) -> None:
    """Persist a point-in-time market constituent observation without symbol inference."""
    conn, owned = _connection(db_path, connection)
    try:
        evidence = relationship.get("evidence_json", {})
        if not isinstance(evidence, str):
            evidence = json.dumps(evidence, default=str, sort_keys=True)
        conn.execute(
            """INSERT INTO asset_relationships VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (market_canonical_id, asset_canonical_id, relationship_type, venue, observed_at, source)
            DO UPDATE SET evidence_json = excluded.evidence_json""",
            [relationship["market_canonical_id"], relationship["asset_canonical_id"],
             relationship["relationship_type"], relationship["venue"], relationship["observed_at"],
             relationship["source"], evidence],
        )
    finally:
        _finish(conn, owned)


def upsert_price_observation(observation: Mapping[str, Any], db_path: str | Path | None = None, *,
                             connection=None) -> None:
    """Persist one provider-normalized, address-scoped market observation."""
    conn, owned = _connection(db_path, connection)
    try:
        evidence = observation.get("evidence_json", {})
        if not isinstance(evidence, str):
            evidence = json.dumps(evidence, default=str, sort_keys=True)
        conn.execute(
            """INSERT INTO price_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (asset_canonical_id, market_canonical_id, observed_at, source)
            DO UPDATE SET price = excluded.price, quote_asset = excluded.quote_asset,
            liquidity_usd = excluded.liquidity_usd, volume_usd = excluded.volume_usd,
            cadence = excluded.cadence, evidence_json = excluded.evidence_json""",
            [observation["asset_canonical_id"], observation["market_canonical_id"],
             observation["observed_at"], observation["price"], observation["quote_asset"],
             observation.get("liquidity_usd"), observation.get("volume_usd"),
             observation["cadence"], observation["source"], evidence],
        )
    finally:
        _finish(conn, owned)


def upsert_metadata(metadata: Mapping[str, Any], db_path: str | Path | None = None, *, connection=None) -> None:
    conn, owned = _connection(db_path, connection)
    try:
        risk_flags = metadata.get("risk_flags_json")
        if risk_flags is not None and not isinstance(risk_flags, str):
            risk_flags = json.dumps(risk_flags, sort_keys=True)
        conn.execute(
            """INSERT INTO metadata VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (canonical_id, last_updated) DO UPDATE SET holder_count = excluded.holder_count,
            lp_locked = excluded.lp_locked, contract_verified = excluded.contract_verified,
            deployer_address = excluded.deployer_address, risk_flags_json = excluded.risk_flags_json,
            last_updated = excluded.last_updated""",
            [metadata["canonical_id"], metadata.get("holder_count"), metadata.get("lp_locked"),
             metadata.get("contract_verified"), metadata.get("deployer_address"), risk_flags,
             metadata["last_updated"]],
        )
    finally:
        _finish(conn, owned)


def log_run_start(job_name: str, db_path: str | Path | None = None, *, started_at: datetime | None = None,
                  run_id: str | None = None, connection=None) -> str:
    run_id = run_id or str(uuid.uuid4())
    conn, owned = _connection(db_path, connection)
    try:
        conn.execute("INSERT INTO runs (run_id, job_name, started_at, status) VALUES (?, ?, ?, ?)",
                     [run_id, job_name, started_at or datetime.now(), "running"])
        return run_id
    finally:
        _finish(conn, owned)


def log_run_end(run_id: str, status: str, db_path: str | Path | None = None, *,
                finished_at: datetime | None = None, rows_written: int = 0,
                error_message: str | None = None, connection=None) -> None:
    conn, owned = _connection(db_path, connection)
    try:
        conn.execute("UPDATE runs SET finished_at = ?, status = ?, rows_written = ?, error_message = ? WHERE run_id = ?",
                     [finished_at or datetime.now(), status, rows_written, error_message, run_id])
    finally:
        _finish(conn, owned)


def _read(table: str, db_path: str | Path | None = None, *, connection=None) -> list[dict[str, Any]]:
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute(f"SELECT * FROM {table}")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)


def read_assets(db_path=None, *, connection=None): return _read("assets", db_path, connection=connection)
def read_ohlcv(db_path=None, *, connection=None): return _read("ohlcv", db_path, connection=connection)
def read_events(db_path=None, *, connection=None): return _read("events", db_path, connection=connection)
def read_metadata(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("SELECT * FROM metadata ORDER BY canonical_id, last_updated")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
def read_runs(db_path=None, *, connection=None): return _read("runs", db_path, connection=connection)
def read_lineage(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("""SELECT * FROM lineage
                               ORDER BY dex_canonical_id, cex_canonical_id, linked_at""")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
def read_asset_relationships(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("""SELECT * FROM asset_relationships
                               ORDER BY market_canonical_id, asset_canonical_id, relationship_type,
                                        venue, observed_at, source""")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)


def read_price_observations(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("""SELECT * FROM price_observations
                               ORDER BY observed_at, asset_canonical_id, market_canonical_id, source""")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
