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
_RATE_LIMIT_ERROR = re.compile(r"(?i)\b(429|rate[ _-]?limit(?:ed)?|too many requests)\b")
_PROVIDER_OBSERVATION_STATUSES = frozenset({"success", "failure", "rate_limited"})


def safe_error_message(error: Exception, limit: int = 500) -> str:
    """Persist useful failure context without copying conventional credentials."""
    message = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", str(error))
    return _SECRET_IN_ERROR.sub(r"\1[REDACTED]", message)[:limit]


def classify_provider_failure(error_message: str | None) -> str:
    """Distinguish a rate-limit gap from a generic provider failure by message evidence."""
    if error_message and _RATE_LIMIT_ERROR.search(error_message):
        return "rate_limited"
    return "failure"


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
        # DuckDB is authoritative. When `committed` is true here, the raised
        # partition(s) failed to publish *after* the DB write already landed,
        # so the two stores now diverge -- `repair_parquet_publication` below
        # is the durable, mechanical recovery path for that state; callers
        # MUST NOT reinterpret this exception as a lost write.
        raise
    finally:
        _finish(conn, owned)


def _partition_dir(root: Path, source: str, partition_date: date) -> Path:
    if not _SAFE_PARTITION_VALUE.fullmatch(str(source)):
        raise ValueError("source must contain only safe partition characters")
    return root / f"source={source}" / f"date={partition_date.isoformat()}"


def _partition_file(root: Path, source: str, partition_date: date) -> Path:
    return _partition_dir(root, source, partition_date) / "part-00000.parquet"


def _select_ohlcv_partition_table(conn, source: str, partition_date: date) -> pa.Table:
    result = conn.execute(
        """SELECT canonical_id, timestamp, open, high, low, close, volume, timeframe, source
        FROM ohlcv WHERE source = ? AND CAST(timestamp AS DATE) = ?
        ORDER BY canonical_id, timestamp, timeframe""", [source, partition_date]
    ).fetchall()
    return pa.Table.from_pylist([dict(zip(_OHLCV_COLUMNS, row)) for row in result])


def _stage_partition_file(table: pa.Table, final: Path) -> Path:
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.{uuid.uuid4().hex}.tmp"
    pq.write_table(table, temporary)
    return temporary


def _write_ohlcv_partitions(conn, rows: list[Mapping[str, Any]], root: Path) -> list[tuple[Path, Path]]:
    partitions = {(row["source"], _as_date(row["timestamp"])) for row in rows}
    staged = []
    for source, partition_date in partitions:
        final = _partition_file(root, source, partition_date)
        table = _select_ohlcv_partition_table(conn, source, partition_date)
        temporary = _stage_partition_file(table, final)
        staged.append((temporary, final))
    return staged


def list_ohlcv_partitions(db_path: str | Path | None = None, *, connection=None) -> list[tuple[str, date]]:
    """Return every (source, partition date) the authoritative OHLCV table currently holds."""
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("SELECT DISTINCT source, CAST(timestamp AS DATE) FROM ohlcv ORDER BY 1, 2")
        return [(row[0], row[1]) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)


def _resolve_parquet_dir(db_path: str | Path | None, parquet_dir: str | Path | None) -> Path:
    if parquet_dir is None and db_path is not None:
        parquet_dir = Path(db_path).parent / "parquet"
    if parquet_dir is None:
        raise ValueError("parquet_dir or db_path is required")
    return Path(parquet_dir)


def verify_parquet_publication(db_path: str | Path | None = None, *, parquet_dir: str | Path | None = None,
                               connection=None) -> list[dict[str, Any]]:
    """Compare every authoritative OHLCV partition against its published Parquet file.

    DuckDB is authoritative; Parquet is a derived publication cache. A
    partition diverges when its file is missing, unreadable, or its content
    does not match what DuckDB currently holds for that (source, date)
    partition -- the state a partial `insert_ohlcv_batch` publication
    failure leaves behind once its DB write has already committed.
    """
    conn, owned = _connection(db_path, connection)
    root = _resolve_parquet_dir(db_path, parquet_dir)
    try:
        divergent = []
        for source, partition_date in list_ohlcv_partitions(connection=conn):
            expected = _select_ohlcv_partition_table(conn, source, partition_date)
            final = _partition_file(root, source, partition_date)
            if not final.exists():
                divergent.append({"source": source, "partition_date": partition_date,
                                  "status": "missing", "path": str(final)})
                continue
            try:
                actual = pq.read_table(final)
            except Exception:
                divergent.append({"source": source, "partition_date": partition_date,
                                  "status": "unreadable", "path": str(final)})
                continue
            if not expected.equals(actual):
                divergent.append({"source": source, "partition_date": partition_date,
                                  "status": "stale", "path": str(final)})
        return divergent
    finally:
        _finish(conn, owned)


def repair_parquet_publication(db_path: str | Path | None = None, *, parquet_dir: str | Path | None = None,
                               connection=None) -> list[dict[str, Any]]:
    """Deterministically rebuild every Parquet partition that diverges from DuckDB.

    Each divergent partition is regenerated in full from the authoritative
    OHLCV rows and published with the same stage-then-atomic-replace
    sequence normal ingestion uses, so a crash mid-repair still leaves every
    partition at either its prior state or its fully repaired state -- never
    a torn file. Repair is idempotent: repeated calls against an already
    repaired store return an empty list.
    """
    conn, owned = _connection(db_path, connection)
    root = _resolve_parquet_dir(db_path, parquet_dir)
    try:
        divergent = verify_parquet_publication(connection=conn, parquet_dir=root)
        repaired = []
        for item in divergent:
            source, partition_date = item["source"], item["partition_date"]
            final = _partition_file(root, source, partition_date)
            table = _select_ohlcv_partition_table(conn, source, partition_date)
            temporary = _stage_partition_file(table, final)
            try:
                os.replace(temporary, final)
            except Exception:
                Path(temporary).unlink(missing_ok=True)
                raise
            repaired.append({**item, "status": "repaired"})
        return repaired
    finally:
        _finish(conn, owned)


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
            SELECT ?, ?, ?, ?, ?, ?, ?, true
            WHERE NOT EXISTS (
                SELECT 1 FROM events
                WHERE canonical_id = ? AND event_type = ? AND timestamp = ? AND source = ?
                  AND COALESCE(block_hash, '') = COALESCE(?, '')
            )""",
            [event["canonical_id"], event["event_type"], event["timestamp"], payload,
             event["source"], event.get("block_number"), event.get("block_hash"),
             event["canonical_id"], event["event_type"], event["timestamp"], event["source"],
             event.get("block_hash")],
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


def get_ingestion_cursor(source: str, scope: str, db_path: str | Path | None = None, *,
                         connection=None) -> dict[str, Any] | None:
    """Return one durable provider progress marker."""
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute(
            """SELECT source, scope, position, updated_at, run_id
               FROM ingestion_cursors WHERE source = ? AND scope = ?""",
            [source, scope],
        )
        row = cursor.fetchone()
        return dict(zip([column[0] for column in cursor.description], row)) if row else None
    finally:
        _finish(conn, owned)


def advance_ingestion_cursor(source: str, scope: str, position: int,
                             db_path: str | Path | None = None, *,
                             updated_at: datetime | None = None, run_id: str | None = None,
                             expected_previous: int | None = None, connection=None) -> None:
    """Advance a cursor monotonically, optionally proving that no range was skipped."""
    if not source or not scope:
        raise ValueError("cursor source and scope are required")
    if isinstance(position, bool) or not isinstance(position, int) or position < 0:
        raise ValueError("cursor position must be a non-negative integer")
    conn, owned = _connection(db_path, connection)
    try:
        conn.execute("BEGIN TRANSACTION")
        current = conn.execute(
            "SELECT position FROM ingestion_cursors WHERE source = ? AND scope = ?",
            [source, scope],
        ).fetchone()
        current_position = current[0] if current else None
        if expected_previous is not None and current_position != expected_previous:
            raise ValueError(
                f"cursor continuity failure for {source}/{scope}: "
                f"expected {expected_previous}, found {current_position}"
            )
        if current_position is not None and position < current_position:
            raise ValueError(
                f"cursor regression for {source}/{scope}: {position} < {current_position}"
            )
        conn.execute(
            """INSERT INTO ingestion_cursors VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (source, scope) DO UPDATE SET
                   position = excluded.position,
                   updated_at = excluded.updated_at,
                   run_id = excluded.run_id""",
            [source, scope, position, updated_at or datetime.now(), run_id],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        _finish(conn, owned)


def get_ingestion_continuation(source: str, scope: str, db_path: str | Path | None = None, *,
                               connection=None) -> dict[str, Any] | None:
    """Return an opaque durable provider continuation token."""
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute(
            """SELECT source, scope, token, updated_at, run_id
               FROM ingestion_continuations WHERE source = ? AND scope = ?""",
            [source, scope],
        )
        row = cursor.fetchone()
        return dict(zip([column[0] for column in cursor.description], row)) if row else None
    finally:
        _finish(conn, owned)


def advance_ingestion_continuation(source: str, scope: str, token: str,
                                   db_path: str | Path | None = None, *,
                                   updated_at: datetime | None = None, run_id: str | None = None,
                                   expected_previous: str | None = None, connection=None) -> None:
    """Replace an opaque token while compare-and-set protects concurrent pollers."""
    if not source or not scope or not isinstance(token, str) or not token:
        raise ValueError("continuation source, scope, and token are required")
    conn, owned = _connection(db_path, connection)
    try:
        conn.execute("BEGIN TRANSACTION")
        current = conn.execute(
            "SELECT token FROM ingestion_continuations WHERE source = ? AND scope = ?",
            [source, scope],
        ).fetchone()
        current_token = current[0] if current else None
        if current_token != expected_previous:
            raise ValueError(
                f"continuation continuity failure for {source}/{scope}: "
                f"expected {expected_previous!r}, found {current_token!r}"
            )
        conn.execute(
            """INSERT INTO ingestion_continuations VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (source, scope) DO UPDATE SET token = excluded.token,
                   updated_at = excluded.updated_at, run_id = excluded.run_id""",
            [source, scope, token, updated_at or datetime.now(), run_id],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        _finish(conn, owned)


def record_evm_block_observation(chain: str, block_number: int, block_hash: str,
                                 parent_hash: str, db_path: str | Path | None = None, *,
                                 observed_at: datetime | None = None, run_id: str | None = None,
                                 connection=None) -> list[dict[str, Any]]:
    """Record a canonical block and retain any hashes it replaces as reorg evidence."""
    if not chain or not block_hash or not parent_hash:
        raise ValueError("chain, block hash, and parent hash are required")
    if isinstance(block_number, bool) or not isinstance(block_number, int) or block_number < 0:
        raise ValueError("block number must be a non-negative integer")
    conn, owned = _connection(db_path, connection)
    try:
        conn.execute("BEGIN TRANSACTION")
        cursor = conn.execute(
            """SELECT block_hash, parent_hash FROM evm_block_observations
               WHERE chain = ? AND block_number = ? AND canonical
               ORDER BY block_hash""", [chain, block_number]
        )
        replaced = [dict(zip([column[0] for column in cursor.description], row))
                    for row in cursor.fetchall() if row[0] != block_hash]
        predecessor = conn.execute(
            """SELECT block_hash FROM evm_block_observations
               WHERE chain = ? AND block_number = ? AND canonical""",
            [chain, block_number - 1],
        ).fetchone()
        if predecessor is not None and predecessor[0] != parent_hash:
            raise ValueError(
                f"non-canonical parent for {chain} block {block_number}: "
                f"expected {predecessor[0]}, found {parent_hash}"
            )
        conn.execute(
            """UPDATE evm_block_observations SET canonical = false
               WHERE chain = ? AND block_number = ? AND block_hash <> ? AND canonical""",
            [chain, block_number, block_hash],
        )
        for old in replaced:
            conn.execute(
                """UPDATE events SET canonical = false
                   WHERE source = 'evm_rpc' AND split_part(canonical_id, ':', 1) = ?
                     AND block_number = ? AND block_hash = ? AND canonical""",
                [chain, block_number, old["block_hash"]],
            )
        conn.execute(
            """INSERT INTO evm_block_observations VALUES (?, ?, ?, ?, ?, true, ?)
               ON CONFLICT (chain, block_number, block_hash) DO UPDATE SET
                   parent_hash = excluded.parent_hash,
                   observed_at = excluded.observed_at,
                   canonical = true,
                   run_id = excluded.run_id""",
            [chain, block_number, block_hash, parent_hash, observed_at or datetime.now(), run_id],
        )
        conn.execute("COMMIT")
        return replaced
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        _finish(conn, owned)


def record_provider_observation(source: str, scope: str, status: str,
                                db_path: str | Path | None = None, *,
                                observed_at: datetime | None = None, latency_ms: float | None = None,
                                expected_interval_seconds: float | None = None, rows_observed: int = 0,
                                error_message: str | None = None, run_id: str | None = None,
                                connection=None) -> dict[str, Any]:
    """Persist one provider poll outcome and derive the observed gap since the prior attempt."""
    if not source or not scope:
        raise ValueError("observation source and scope are required")
    if status not in _PROVIDER_OBSERVATION_STATUSES:
        raise ValueError(f"unsupported provider observation status: {status!r}")
    observed_at = observed_at or datetime.now()
    conn, owned = _connection(db_path, connection)
    try:
        conn.execute("BEGIN TRANSACTION")
        previous = conn.execute(
            "SELECT MAX(observed_at) FROM provider_observation_log WHERE source = ? AND scope = ?",
            [source, scope],
        ).fetchone()[0]
        naive_observed_at = observed_at.replace(tzinfo=None) if observed_at.tzinfo is not None else observed_at
        observed_interval_seconds = (
            (naive_observed_at - previous).total_seconds() if previous is not None else None
        )
        conn.execute(
            "INSERT INTO provider_observation_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [source, scope, observed_at, status, latency_ms, expected_interval_seconds,
             observed_interval_seconds, rows_observed, error_message, run_id],
        )
        conn.execute("COMMIT")
        return {"source": source, "scope": scope, "observed_at": observed_at, "status": status,
                "latency_ms": latency_ms, "expected_interval_seconds": expected_interval_seconds,
                "observed_interval_seconds": observed_interval_seconds, "rows_observed": rows_observed,
                "error_message": error_message, "run_id": run_id}
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        _finish(conn, owned)


def provider_quality_summary(db_path: str | Path | None = None, *, connection=None) -> list[dict[str, Any]]:
    """Aggregate offline provider quality facts by source/scope for research eligibility checks."""
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute(
            """SELECT source, scope,
                      COUNT(*) AS total_observations,
                      SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                      SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) AS failure_count,
                      SUM(CASE WHEN status = 'rate_limited' THEN 1 ELSE 0 END) AS rate_limited_count,
                      AVG(latency_ms) AS avg_latency_ms,
                      MAX(observed_interval_seconds) AS max_observed_gap_seconds,
                      arg_max(expected_interval_seconds, observed_at) AS expected_interval_seconds,
                      arg_max(status, observed_at) AS last_status,
                      MAX(observed_at) AS last_observed_at
               FROM provider_observation_log
               GROUP BY source, scope
               ORDER BY source, scope"""
        )
        rows = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        for row in rows:
            row["completeness_ratio"] = (
                row["success_count"] / row["total_observations"] if row["total_observations"] else None
            )
        return rows
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
def read_events(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("SELECT * FROM events WHERE canonical ORDER BY timestamp, canonical_id, event_type, source")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
def read_event_history(db_path=None, *, connection=None): return _read("events", db_path, connection=connection)
def read_metadata(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("SELECT * FROM metadata ORDER BY canonical_id, last_updated")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
def read_runs(db_path=None, *, connection=None): return _read("runs", db_path, connection=connection)
def read_ingestion_cursors(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("""SELECT * FROM ingestion_cursors
                               ORDER BY source, scope""")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
def read_ingestion_continuations(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("""SELECT * FROM ingestion_continuations
                               ORDER BY source, scope""")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
def read_evm_block_observations(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("""SELECT * FROM evm_block_observations
                               ORDER BY chain, block_number, block_hash""")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
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


def read_provider_observation_log(db_path=None, *, connection=None):
    conn, owned = _connection(db_path, connection)
    try:
        cursor = conn.execute("""SELECT * FROM provider_observation_log
                               ORDER BY source, scope, observed_at""")
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    finally:
        _finish(conn, owned)
