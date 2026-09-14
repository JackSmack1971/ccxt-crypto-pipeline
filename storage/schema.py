"""Canonical DuckDB schema for the Phase 1 persistence boundary."""

from __future__ import annotations

import duckdb

SCHEMA_VERSION = 11

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
    PRIMARY KEY (canonical_id, timestamp, timeframe, source)
);

CREATE TABLE IF NOT EXISTS events (
    canonical_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    payload_json VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    block_number BIGINT,
    block_hash VARCHAR,
    canonical BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS metadata (
    canonical_id VARCHAR NOT NULL,
    holder_count BIGINT,
    lp_locked BOOLEAN,
    contract_verified BOOLEAN,
    deployer_address VARCHAR,
    risk_flags_json VARCHAR,
    last_updated TIMESTAMP NOT NULL,
    PRIMARY KEY (canonical_id, last_updated)
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
    PRIMARY KEY (dex_canonical_id, cex_canonical_id, linked_at)
);

CREATE TABLE IF NOT EXISTS asset_relationships (
    market_canonical_id VARCHAR NOT NULL,
    asset_canonical_id VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL CHECK (relationship_type IN ('base', 'quote', 'constituent_0', 'constituent_1')),
    venue VARCHAR NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,
    evidence_json VARCHAR NOT NULL,
    PRIMARY KEY (market_canonical_id, asset_canonical_id, relationship_type, venue, observed_at, source)
);

CREATE TABLE IF NOT EXISTS price_observations (
    asset_canonical_id VARCHAR NOT NULL,
    market_canonical_id VARCHAR NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    price DOUBLE NOT NULL CHECK (price > 0),
    quote_asset VARCHAR NOT NULL,
    liquidity_usd DOUBLE CHECK (liquidity_usd IS NULL OR liquidity_usd >= 0),
    volume_usd DOUBLE CHECK (volume_usd IS NULL OR volume_usd >= 0),
    cadence VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    evidence_json VARCHAR NOT NULL,
    PRIMARY KEY (asset_canonical_id, market_canonical_id, observed_at, source)
);

CREATE TABLE IF NOT EXISTS ingestion_cursors (
    source VARCHAR NOT NULL,
    scope VARCHAR NOT NULL,
    position BIGINT NOT NULL CHECK (position >= 0),
    updated_at TIMESTAMP NOT NULL,
    run_id VARCHAR,
    PRIMARY KEY (source, scope)
);

CREATE TABLE IF NOT EXISTS ingestion_continuations (
    source VARCHAR NOT NULL,
    scope VARCHAR NOT NULL,
    token VARCHAR NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    run_id VARCHAR,
    PRIMARY KEY (source, scope)
);

CREATE TABLE IF NOT EXISTS evm_block_observations (
    chain VARCHAR NOT NULL,
    block_number BIGINT NOT NULL CHECK (block_number >= 0),
    block_hash VARCHAR NOT NULL,
    parent_hash VARCHAR NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    canonical BOOLEAN NOT NULL,
    run_id VARCHAR,
    PRIMARY KEY (chain, block_number, block_hash)
);

CREATE TABLE IF NOT EXISTS provider_observation_log (
    source VARCHAR NOT NULL,
    scope VARCHAR NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('success', 'failure', 'rate_limited')),
    latency_ms DOUBLE CHECK (latency_ms IS NULL OR latency_ms >= 0),
    expected_interval_seconds DOUBLE CHECK (expected_interval_seconds IS NULL OR expected_interval_seconds > 0),
    observed_interval_seconds DOUBLE CHECK (observed_interval_seconds IS NULL OR observed_interval_seconds >= 0),
    rows_observed BIGINT NOT NULL DEFAULT 0,
    error_message VARCHAR,
    run_id VARCHAR,
    PRIMARY KEY (source, scope, observed_at)
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
    if versions[0] < 3:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE metadata_v3 (
                canonical_id VARCHAR NOT NULL,
                holder_count BIGINT,
                lp_locked BOOLEAN,
                contract_verified BOOLEAN,
                deployer_address VARCHAR,
                risk_flags_json VARCHAR,
                last_updated TIMESTAMP NOT NULL,
                PRIMARY KEY (canonical_id, last_updated)
            )""")
            connection.execute("""INSERT INTO metadata_v3
                (canonical_id, holder_count, lp_locked, contract_verified,
                 deployer_address, risk_flags_json, last_updated)
                SELECT canonical_id, holder_count, lp_locked, contract_verified,
                       deployer_address, risk_flags_json, last_updated
                FROM metadata""")
            connection.execute("DROP TABLE metadata")
            connection.execute("ALTER TABLE metadata_v3 RENAME TO metadata")
            connection.execute("UPDATE schema_version SET version = 3")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (3,)
    if versions[0] < 4:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE lineage_v4 (
                dex_canonical_id VARCHAR NOT NULL,
                cex_canonical_id VARCHAR NOT NULL,
                linked_at TIMESTAMP NOT NULL,
                PRIMARY KEY (dex_canonical_id, cex_canonical_id, linked_at)
            )""")
            connection.execute("""INSERT INTO lineage_v4
                (dex_canonical_id, cex_canonical_id, linked_at)
                SELECT dex_canonical_id, cex_canonical_id, linked_at FROM lineage""")
            connection.execute("DROP TABLE lineage")
            connection.execute("ALTER TABLE lineage_v4 RENAME TO lineage")
            connection.execute("UPDATE schema_version SET version = 4")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (4,)
    if versions[0] < 5:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE ohlcv_v5 (
                canonical_id VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open DOUBLE NOT NULL,
                high DOUBLE NOT NULL,
                low DOUBLE NOT NULL,
                close DOUBLE NOT NULL,
                volume DOUBLE NOT NULL,
                timeframe VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                PRIMARY KEY (canonical_id, timestamp, timeframe, source)
            )""")
            connection.execute("""INSERT INTO ohlcv_v5
                (canonical_id, timestamp, open, high, low, close, volume, timeframe, source)
                SELECT canonical_id, timestamp, open, high, low, close, volume, timeframe, source
                FROM ohlcv""")
            connection.execute("DROP TABLE ohlcv")
            connection.execute("ALTER TABLE ohlcv_v5 RENAME TO ohlcv")
            connection.execute("UPDATE schema_version SET version = 5")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (5,)
    if versions[0] < 6:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS asset_relationships (
                market_canonical_id VARCHAR NOT NULL,
                asset_canonical_id VARCHAR NOT NULL,
                relationship_type VARCHAR NOT NULL CHECK (relationship_type IN ('base', 'quote', 'constituent_0', 'constituent_1')),
                venue VARCHAR NOT NULL,
                observed_at TIMESTAMP NOT NULL,
                source VARCHAR NOT NULL,
                evidence_json VARCHAR NOT NULL,
                PRIMARY KEY (market_canonical_id, asset_canonical_id, relationship_type, venue, observed_at, source)
            )""")
            connection.execute("UPDATE schema_version SET version = 6")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (6,)
    if versions[0] < 7:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS price_observations (
                asset_canonical_id VARCHAR NOT NULL,
                market_canonical_id VARCHAR NOT NULL,
                observed_at TIMESTAMP NOT NULL,
                price DOUBLE NOT NULL CHECK (price > 0),
                quote_asset VARCHAR NOT NULL,
                liquidity_usd DOUBLE CHECK (liquidity_usd IS NULL OR liquidity_usd >= 0),
                volume_usd DOUBLE CHECK (volume_usd IS NULL OR volume_usd >= 0),
                cadence VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                evidence_json VARCHAR NOT NULL,
                PRIMARY KEY (asset_canonical_id, market_canonical_id, observed_at, source)
            )""")
            connection.execute("UPDATE schema_version SET version = ?", [SCHEMA_VERSION])
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (7,)
    if versions[0] < 8:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS ingestion_cursors (
                source VARCHAR NOT NULL,
                scope VARCHAR NOT NULL,
                position BIGINT NOT NULL CHECK (position >= 0),
                updated_at TIMESTAMP NOT NULL,
                run_id VARCHAR,
                PRIMARY KEY (source, scope)
            )""")
            connection.execute("UPDATE schema_version SET version = ?", [SCHEMA_VERSION])
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (8,)
    if versions[0] < 9:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS block_number BIGINT")
            connection.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS block_hash VARCHAR")
            connection.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS canonical BOOLEAN DEFAULT true")
            connection.execute("UPDATE events SET canonical = true WHERE canonical IS NULL")
            connection.execute("ALTER TABLE events ALTER COLUMN canonical SET NOT NULL")
            connection.execute("""CREATE TABLE IF NOT EXISTS evm_block_observations (
                chain VARCHAR NOT NULL,
                block_number BIGINT NOT NULL CHECK (block_number >= 0),
                block_hash VARCHAR NOT NULL,
                parent_hash VARCHAR NOT NULL,
                observed_at TIMESTAMP NOT NULL,
                canonical BOOLEAN NOT NULL,
                run_id VARCHAR,
                PRIMARY KEY (chain, block_number, block_hash)
            )""")
            connection.execute("UPDATE schema_version SET version = ?", [SCHEMA_VERSION])
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (9,)
    if versions[0] < 10:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS ingestion_continuations (
                source VARCHAR NOT NULL,
                scope VARCHAR NOT NULL,
                token VARCHAR NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                run_id VARCHAR,
                PRIMARY KEY (source, scope)
            )""")
            connection.execute("UPDATE schema_version SET version = ?", [SCHEMA_VERSION])
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        versions = (10,)
    if versions[0] < 11:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS provider_observation_log (
                source VARCHAR NOT NULL,
                scope VARCHAR NOT NULL,
                observed_at TIMESTAMP NOT NULL,
                status VARCHAR NOT NULL CHECK (status IN ('success', 'failure', 'rate_limited')),
                latency_ms DOUBLE CHECK (latency_ms IS NULL OR latency_ms >= 0),
                expected_interval_seconds DOUBLE CHECK (expected_interval_seconds IS NULL OR expected_interval_seconds > 0),
                observed_interval_seconds DOUBLE CHECK (observed_interval_seconds IS NULL OR observed_interval_seconds >= 0),
                rows_observed BIGINT NOT NULL DEFAULT 0,
                error_message VARCHAR,
                run_id VARCHAR,
                PRIMARY KEY (source, scope, observed_at)
            )""")
            connection.execute("UPDATE schema_version SET version = ?", [SCHEMA_VERSION])
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
