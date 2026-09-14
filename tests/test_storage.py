from datetime import datetime, timezone

from storage.db import (
    SCHEMA_VERSION,
    advance_ingestion_cursor,
    get_ingestion_cursor,
    init_db,
    insert_event,
    insert_ohlcv_batch,
    log_run_end,
    log_run_start,
    read_assets,
    read_asset_relationships,
    read_events,
    read_ingestion_cursors,
    read_metadata,
    read_ohlcv,
    read_price_observations,
    read_lineage,
    read_runs,
    safe_error_message,
    upsert_asset,
    upsert_asset_relationship,
    upsert_metadata,
    upsert_price_observation,
)
import duckdb


def test_storage_round_trip_and_idempotent_init(tmp_path):
    db_path = tmp_path / "pipeline.duckdb"
    parquet_dir = tmp_path / "parquet"
    timestamp = datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc)

    init_db(db_path)
    init_db(db_path)
    upsert_asset({"canonical_id": "kraken:BTC/USDT", "source_type": "cex",
                  "chain_or_exchange": "kraken", "symbol_or_contract": "BTC/USDT",
                  "first_seen": timestamp}, db_path)
    insert_ohlcv_batch([{"canonical_id": "kraken:BTC/USDT", "timestamp": timestamp,
                         "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
                         "volume": 10.0, "timeframe": "1d", "source": "kraken"}],
                       db_path, parquet_dir=parquet_dir)
    insert_ohlcv_batch([{"canonical_id": "kraken:BTC/USDT", "timestamp": timestamp,
                         "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
                         "volume": 10.0, "timeframe": "1d", "source": "kraken"}],
                       db_path, parquet_dir=parquet_dir)
    insert_event({"canonical_id": "ethereum:0xpool", "event_type": "new_pool_detected",
                  "timestamp": timestamp, "payload_json": {"pair": "ABC/USDT"},
                  "source": "fixture"}, db_path)
    upsert_metadata({"canonical_id": "ethereum:0xtoken", "holder_count": 7,
                     "lp_locked": True, "contract_verified": False,
                     "deployer_address": "0xdeployer", "risk_flags_json": {"honeypot": False},
                     "last_updated": timestamp}, db_path)
    run_id = log_run_start("fixture_job", db_path, started_at=timestamp, run_id="run-1")
    log_run_end(run_id, "success", db_path, finished_at=timestamp, rows_written=1)

    assert SCHEMA_VERSION == 8
    asset = read_assets(db_path)[0]
    assert (asset["canonical_id"], asset["source_type"], asset["chain_or_exchange"],
            asset["symbol_or_contract"]) == ("kraken:BTC/USDT", "cex", "kraken", "BTC/USDT")
    ohlcv = read_ohlcv(db_path)[0]
    assert (ohlcv["canonical_id"], ohlcv["open"], ohlcv["high"], ohlcv["low"],
            ohlcv["close"], ohlcv["volume"], ohlcv["timeframe"], ohlcv["source"]) == (
                "kraken:BTC/USDT", 1.0, 2.0, 0.5, 1.5, 10.0, "1d", "kraken")
    assert len(read_ohlcv(db_path)) == 1
    event = read_events(db_path)[0]
    assert (event["canonical_id"], event["event_type"], event["payload_json"], event["source"]) == (
        "ethereum:0xpool", "new_pool_detected", '{"pair": "ABC/USDT"}', "fixture")
    metadata = read_metadata(db_path)[0]
    assert (metadata["canonical_id"], metadata["holder_count"], metadata["lp_locked"],
            metadata["contract_verified"], metadata["deployer_address"], metadata["risk_flags_json"]) == (
                "ethereum:0xtoken", 7, True, False, "0xdeployer", '{"honeypot": false}')
    run = read_runs(db_path)[0]
    assert (run["run_id"], run["job_name"], run["status"], run["rows_written"], run["error_message"]) == (
        "run-1", "fixture_job", "success", 1, None)
    assert list(parquet_dir.glob("source=kraken/date=2025-01-02/*.parquet"))


def test_v1_store_migrates_in_place_and_preserves_rows(tmp_path):
    db_path = tmp_path / "v1.duckdb"
    connection = duckdb.connect(str(db_path))
    connection.execute("""CREATE TABLE assets (
        canonical_id VARCHAR PRIMARY KEY, source_type VARCHAR NOT NULL,
        chain_or_exchange VARCHAR NOT NULL, symbol_or_contract VARCHAR NOT NULL,
        first_seen TIMESTAMP NOT NULL)""")
    connection.execute("INSERT INTO assets VALUES ('kraken:BTC/USDT', 'cex', 'kraken', 'BTC/USDT', ?)",
                       [datetime(2025, 1, 1)])
    connection.execute("""CREATE TABLE metadata (
        canonical_id VARCHAR PRIMARY KEY, holder_count BIGINT, lp_locked BOOLEAN,
        contract_verified BOOLEAN, deployer_address VARCHAR, risk_flags_json VARCHAR,
        last_updated TIMESTAMP NOT NULL)""")
    connection.execute("INSERT INTO metadata VALUES ('kraken:BTC/USDT', 3, NULL, NULL, NULL, NULL, ?)",
                       [datetime(2025, 1, 2)])
    connection.execute("""CREATE TABLE lineage (
        dex_canonical_id VARCHAR NOT NULL, cex_canonical_id VARCHAR NOT NULL,
        linked_at TIMESTAMP NOT NULL,
        PRIMARY KEY (dex_canonical_id, cex_canonical_id))""")
    connection.execute("INSERT INTO lineage VALUES ('ethereum:0xabc', 'kraken:ABC/USD', ?)",
                       [datetime(2025, 1, 3)])
    connection.execute("""CREATE TABLE ohlcv (
        canonical_id VARCHAR NOT NULL, timestamp TIMESTAMP NOT NULL,
        open DOUBLE NOT NULL, high DOUBLE NOT NULL, low DOUBLE NOT NULL,
        close DOUBLE NOT NULL, volume DOUBLE NOT NULL, timeframe VARCHAR NOT NULL,
        source VARCHAR NOT NULL, PRIMARY KEY (canonical_id, timestamp, timeframe))""")
    connection.execute("INSERT INTO ohlcv VALUES ('ethereum:0xabc', ?, 1, 1, 1, 1, 1, '1d', 'fixture')",
                       [datetime(2025, 1, 3)])
    connection.close()

    init_db(db_path)
    connection = duckdb.connect(str(db_path))
    assert connection.execute("SELECT version FROM schema_version").fetchone() == (8,)
    assert connection.execute("SELECT contract_address FROM assets").fetchone() == (None,)
    assert connection.execute("SELECT COUNT(*) FROM lineage").fetchone() == (1,)
    assert connection.execute("SELECT canonical_id FROM assets").fetchone() == ("kraken:BTC/USDT",)
    assert connection.execute("SELECT canonical_id, holder_count FROM metadata").fetchone() == ("kraken:BTC/USDT", 3)
    assert connection.execute("SELECT dex_canonical_id, cex_canonical_id FROM lineage").fetchone() == (
        "ethereum:0xabc", "kraken:ABC/USD")
    assert connection.execute("SELECT canonical_id, source FROM ohlcv").fetchone() == ("ethereum:0xabc", "fixture")
    assert connection.execute("SELECT dex_canonical_id, cex_canonical_id FROM lineage").fetchone() == (
        "ethereum:0xabc", "kraken:ABC/USD")
    migrated_signature = connection.execute(
        """SELECT table_name, column_name, data_type, ordinal_position
           FROM information_schema.columns
           WHERE table_schema = 'main' ORDER BY table_name, ordinal_position"""
    ).fetchall()
    connection.close()

    fresh_path = tmp_path / "fresh.duckdb"
    init_db(fresh_path)
    fresh = duckdb.connect(str(fresh_path))
    fresh_signature = fresh.execute(
        """SELECT table_name, column_name, data_type, ordinal_position
           FROM information_schema.columns
           WHERE table_schema = 'main' ORDER BY table_name, ordinal_position"""
    ).fetchall()
    assert migrated_signature == fresh_signature
    fresh.close()
    init_db(db_path)
    repeat = duckdb.connect(str(db_path))
    assert repeat.execute("SELECT version FROM schema_version").fetchone() == (8,)
    assert repeat.execute("SELECT COUNT(*) FROM metadata").fetchone() == (1,)
    assert repeat.execute("SELECT COUNT(*) FROM lineage").fetchone() == (1,)
    assert repeat.execute("SELECT COUNT(*) FROM ohlcv").fetchone() == (1,)
    repeat.close()


def test_v5_store_adds_identity_relationship_contract_without_losing_rows(tmp_path):
    db_path = tmp_path / "v5.duckdb"
    connection = duckdb.connect(str(db_path))
    connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_version VALUES (5)")
    # The v5 fixture uses the complete old schema to exercise the supported upgrade.
    from storage.schema import SCHEMA_SQL
    for statement in SCHEMA_SQL.split(";"):
        if statement.strip() and not any(name in statement for name in ("asset_relationships", "price_observations")):
            connection.execute(statement)
    connection.execute("INSERT INTO assets VALUES ('ethereum:0xpool', 'dex', 'ethereum', '0xpool', ?, NULL)",
                       [datetime(2025, 1, 1)])
    connection.close()

    init_db(db_path)
    connection = duckdb.connect(str(db_path))
    assert connection.execute("SELECT version FROM schema_version").fetchone() == (8,)
    assert connection.execute("SELECT canonical_id FROM assets").fetchone() == ("ethereum:0xpool",)
    assert connection.execute("SELECT COUNT(*) FROM asset_relationships").fetchone() == (0,)
    connection.close()

def test_v6_store_adds_price_observation_contract_without_losing_rows(tmp_path):
    db_path = tmp_path / "v6.duckdb"
    connection = duckdb.connect(str(db_path))
    connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_version VALUES (6)")
    from storage.schema import SCHEMA_SQL
    for statement in SCHEMA_SQL.split(";"):
        if statement.strip() and "price_observations" not in statement:
            connection.execute(statement)
    connection.execute("INSERT INTO assets VALUES ('ethereum:0xpool', 'dex', 'ethereum', '0xpool', ?, NULL)",
                       [datetime(2025, 1, 1)])
    connection.close()

    init_db(db_path)
    connection = duckdb.connect(str(db_path))
    assert connection.execute("SELECT version FROM schema_version").fetchone() == (8,)
    assert connection.execute("SELECT canonical_id FROM assets").fetchone() == ("ethereum:0xpool",)
    assert connection.execute("SELECT COUNT(*) FROM asset_relationships").fetchone() == (0,)
    connection.close()

    init_db(db_path)
    connection = duckdb.connect(str(db_path))
    assert connection.execute("SELECT version FROM schema_version").fetchone() == (8,)
    assert connection.execute("SELECT COUNT(*) FROM price_observations").fetchone() == (0,)
    connection.close()


def test_v7_store_adds_ingestion_cursors_without_losing_rows(tmp_path):
    db_path = tmp_path / "v7.duckdb"
    connection = duckdb.connect(str(db_path))
    connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_version VALUES (7)")
    from storage.schema import SCHEMA_SQL
    for statement in SCHEMA_SQL.split(";"):
        if statement.strip() and "ingestion_cursors" not in statement:
            connection.execute(statement)
    connection.execute("INSERT INTO assets VALUES ('ethereum:0xpool', 'dex', 'ethereum', '0xpool', ?, NULL)",
                       [datetime(2025, 1, 1)])
    connection.close()

    init_db(db_path)
    connection = duckdb.connect(str(db_path))
    assert connection.execute("SELECT version FROM schema_version").fetchone() == (8,)
    assert connection.execute("SELECT canonical_id FROM assets").fetchone() == ("ethereum:0xpool",)
    assert connection.execute("SELECT COUNT(*) FROM ingestion_cursors").fetchone() == (0,)
    connection.close()


def test_ingestion_cursor_is_scoped_monotonic_and_continuity_checked(tmp_path):
    db_path = tmp_path / "cursors.duckdb"
    observed = datetime(2025, 1, 1, tzinfo=timezone.utc)
    advance_ingestion_cursor("evm_rpc", "ethereum", 100, db_path,
                             updated_at=observed, run_id="run-1")
    advance_ingestion_cursor("evm_rpc", "base", 50, db_path,
                             updated_at=observed, run_id="run-2")
    advance_ingestion_cursor("evm_rpc", "ethereum", 101, db_path,
                             updated_at=observed, run_id="run-3", expected_previous=100)

    assert get_ingestion_cursor("evm_rpc", "ethereum", db_path)["position"] == 101
    assert [(row["scope"], row["position"]) for row in read_ingestion_cursors(db_path)] == [
        ("base", 50), ("ethereum", 101)
    ]
    for position, expected_previous, message in ((99, None, "cursor regression"),
                                                  (102, 100, "cursor continuity failure")):
        try:
            advance_ingestion_cursor("evm_rpc", "ethereum", position, db_path,
                                     expected_previous=expected_previous)
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError("invalid cursor advance should fail")
    assert get_ingestion_cursor("evm_rpc", "ethereum", db_path)["position"] == 101


def test_price_observation_round_trip_is_idempotent_and_ordered(tmp_path):
    db_path = tmp_path / "observations.duckdb"
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    observation = {"asset_canonical_id": "ethereum:0xbase", "market_canonical_id": "ethereum:0xpool",
                   "observed_at": timestamp, "price": 1.25, "quote_asset": "USD",
                   "liquidity_usd": 12000, "volume_usd": 500, "cadence": "20m",
                   "source": "fixture", "evidence_json": {"fixture": True}}
    upsert_price_observation(observation, db_path)
    upsert_price_observation({**observation, "price": 1.5}, db_path)
    rows = read_price_observations(db_path)
    assert len(rows) == 1
    assert (rows[0]["asset_canonical_id"], rows[0]["market_canonical_id"], rows[0]["price"],
            rows[0]["quote_asset"], rows[0]["cadence"], rows[0]["evidence_json"]) == (
                "ethereum:0xbase", "ethereum:0xpool", 1.5, "USD", "20m", '{"fixture": true}')

def test_asset_relationships_round_trip_point_in_time_evidence(tmp_path):
    db_path = tmp_path / "relationships.duckdb"
    observed = datetime(2025, 1, 1)
    for address in ("0xpool", "0xbase", "0xquote"):
        upsert_asset({"canonical_id": f"ethereum:{address}", "source_type": "dex",
                      "chain_or_exchange": "ethereum", "symbol_or_contract": address,
                      "first_seen": observed}, db_path)
    for role, address in (("base", "0xbase"), ("quote", "0xquote")):
        upsert_asset_relationship({"market_canonical_id": "ethereum:0xpool",
                                   "asset_canonical_id": f"ethereum:{address}",
                                   "relationship_type": role, "venue": "fixture-dex",
                                   "observed_at": observed, "source": "fixture",
                                   "evidence_json": {"role": role}}, db_path)
    rows = read_asset_relationships(db_path)
    assert [(row["relationship_type"], row["asset_canonical_id"]) for row in rows] == [
        ("base", "ethereum:0xbase"), ("quote", "ethereum:0xquote")]
    assert rows[0]["evidence_json"] == '{"role": "base"}'


def test_metadata_observations_preserve_point_in_time_history_and_are_idempotent(tmp_path):
    db_path = tmp_path / "metadata-history.duckdb"
    timestamp = datetime(2025, 1, 1)
    upsert_asset({"canonical_id": "ethereum:0xabc", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xabc",
                  "first_seen": timestamp}, db_path)
    upsert_metadata({"canonical_id": "ethereum:0xabc", "holder_count": 10,
                     "last_updated": timestamp}, db_path)
    upsert_metadata({"canonical_id": "ethereum:0xabc", "holder_count": 20,
                     "last_updated": timestamp.replace(day=2)}, db_path)
    upsert_metadata({"canonical_id": "ethereum:0xabc", "holder_count": 11,
                     "last_updated": timestamp}, db_path)

    assert [(row["holder_count"], row["last_updated"]) for row in read_metadata(db_path)] == [
        (11, timestamp), (20, timestamp.replace(day=2))
    ]


def test_asset_identity_preserves_earliest_observation_boundary(tmp_path):
    db_path = tmp_path / "asset-history.duckdb"
    first = datetime(2025, 1, 1)
    later = datetime(2025, 1, 3)
    upsert_asset({"canonical_id": "ethereum:0xabc", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xabc",
                  "first_seen": first}, db_path)
    upsert_asset({"canonical_id": "ethereum:0xabc", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xabc",
                  "first_seen": later}, db_path)
    assert read_assets(db_path)[0]["first_seen"] == first


def test_lineage_observations_preserve_point_in_time_history_and_are_idempotent(tmp_path):
    db_path = tmp_path / "lineage-history.duckdb"
    first = datetime(2025, 1, 1)
    second = datetime(2025, 1, 2)
    from normalization.reconcile import reconcile_assets
    upsert_asset({"canonical_id": "ethereum:0xabc", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xabc",
                  "first_seen": first}, db_path)
    upsert_asset({"canonical_id": "kraken:ABC/USD", "source_type": "cex",
                  "chain_or_exchange": "kraken", "symbol_or_contract": "ABC/USD",
                  "contract_address": "0xabc", "first_seen": first}, db_path)

    assert len(reconcile_assets(str(db_path), linked_at=first)) == 1
    assert len(reconcile_assets(str(db_path), linked_at=first)) == 1
    assert len(reconcile_assets(str(db_path), linked_at=second)) == 1
    assert [(row["linked_at"], row["dex_canonical_id"], row["cex_canonical_id"])
            for row in read_lineage(db_path)] == [
                (first, "ethereum:0xabc", "kraken:ABC/USD"),
                (second, "ethereum:0xabc", "kraken:ABC/USD"),
            ]


def test_same_time_events_from_distinct_sources_are_preserved(tmp_path):
    db_path = tmp_path / "events.duckdb"
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    upsert_asset({"canonical_id": "ethereum:0xpool", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xpool",
                  "first_seen": timestamp}, db_path)
    for source in ("geckoterminal", "evm_rpc"):
        insert_event({"canonical_id": "ethereum:0xpool", "event_type": "new_pool_detected",
                      "timestamp": timestamp, "payload_json": {"source": source},
                      "source": source}, db_path)
    assert {row["source"] for row in read_events(db_path)} == {"geckoterminal", "evm_rpc"}


def test_storage_error_messages_redact_urls_and_credentials():
    message = safe_error_message(ValueError("https://user:pass@example.test api_key=top-secret"))
    assert "user:pass" not in message
    assert "top-secret" not in message
