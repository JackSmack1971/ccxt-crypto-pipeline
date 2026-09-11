from datetime import datetime, timezone

from storage.db import (
    SCHEMA_VERSION,
    init_db,
    insert_event,
    insert_ohlcv_batch,
    log_run_end,
    log_run_start,
    read_assets,
    read_events,
    read_metadata,
    read_ohlcv,
    read_runs,
    safe_error_message,
    upsert_asset,
    upsert_metadata,
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

    assert SCHEMA_VERSION == 2
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
    connection.close()

    init_db(db_path)
    connection = duckdb.connect(str(db_path))
    assert connection.execute("SELECT version FROM schema_version").fetchone() == (2,)
    assert connection.execute("SELECT contract_address FROM assets").fetchone() == (None,)
    assert connection.execute("SELECT COUNT(*) FROM lineage").fetchone() == (0,)
    assert connection.execute("SELECT canonical_id FROM assets").fetchone() == ("kraken:BTC/USDT",)
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
