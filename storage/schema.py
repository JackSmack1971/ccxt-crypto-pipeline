"""Canonical DuckDB schema for the Phase 1 persistence boundary."""

from __future__ import annotations

import duckdb

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS assets (
    canonical_id VARCHAR PRIMARY KEY,
    source_type VARCHAR NOT NULL CHECK (source_type IN ('cex', 'dex')),
    chain_or_exchange VARCHAR NOT NULL,
    symbol_or_contract VARCHAR NOT NULL,
    first_seen TIMESTAMP NOT NULL,
    contract_address VARCHAR
);

CREATE TABLE IF NOT EXISTS ohlcv (
    canonical_id VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DOUBLE NOT NULL,
    high DOUBLE NOT NULL,
    low DOUBLE NOT NULL,
    close DOUBLE NOT NULL,
    volume DOUBLE NOT NULL,
    timeframe VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    PRIMARY KEY (canonical_id, timestamp, timeframe)
);

CREATE TABLE IF NOT EXISTS events (
    canonical_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    payload_json VARCHAR NOT NULL,
    source VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata (
    canonical_id VARCHAR PRIMARY KEY,
    holder_count BIGINT,
    lp_locked BOOLEAN,
    contract_verified BOOLEAN,
    deployer_address VARCHAR,
    risk_flags_json VARCHAR,
    last_updated TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY,
    job_name VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status VARCHAR NOT NULL,
    rows_written BIGINT NOT NULL DEFAULT 0,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS lineage (
    dex_canonical_id VARCHAR NOT NULL,
    cex_canonical_id VARCHAR NOT NULL,
    linked_at TIMESTAMP NOT NULL,
    PRIMARY KEY (dex_canonical_id, cex_canonical_id)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""


def initialize(connection: duckdb.DuckDBPyConnection) -> None:
    """Create or safely upgrade the complete target schema."""
    had_assets = connection.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'assets'"
    ).fetchone()[0] > 0
    connection.execute(SCHEMA_SQL)
    connection.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS contract_address VARCHAR")

    versions = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if versions is None:
        # Databases created by Goal 1 predate the version ledger and are version 1.
        connection.execute("INSERT INTO schema_version VALUES (?)", [1 if had_assets else SCHEMA_VERSION])
        versions = (1 if had_assets else SCHEMA_VERSION,)
    if versions[0] > SCHEMA_VERSION:
        raise RuntimeError(f"database schema {versions[0]} is newer than supported {SCHEMA_VERSION}")
    if versions[0] < SCHEMA_VERSION:
        connection.execute("UPDATE schema_version SET version = ?", [SCHEMA_VERSION])
