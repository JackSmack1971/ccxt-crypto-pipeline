from datetime import datetime, timezone

from normalization.reconcile import (_address_key, data_quality_report, daily_ingestion_summary,
                                     reconcile_assets)
from storage.db import read_lineage, upsert_asset


def test_address_key_preserves_canonical_case_and_separator_boundaries():
    assert _address_key("ethereum", "  0xAbC/Def  ") == "0xabc/def"
    assert _address_key("ethereum", "0xabc-def") == "0xabc-def"
    assert _address_key("ethereum", "0xabc/def") != _address_key("ethereum", "0xabc-def")
    assert _address_key("solana", "  AbC/Def  ") == "AbC/Def"
    assert _address_key("solana", "AbC/Def") != _address_key("solana", "abc/def")


def test_address_key_merges_non_solana_case_and_whitespace_only():
    assert _address_key("ethereum", "  0xAbC  ") == _address_key("ethereum", "0xabc")
    assert _address_key("ethereum", "0xabc") == "0xabc"


def test_real_usdc_contract_links_dex_and_cex_identity(tmp_path):
    db = str(tmp_path / "pipeline.duckdb")
    address = "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # Ethereum USDC
    first_seen = datetime(2025, 1, 1, tzinfo=timezone.utc)
    upsert_asset({"canonical_id": f"ethereum:{address}", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": address,
                  "first_seen": first_seen}, db)
    upsert_asset({"canonical_id": "kraken:USDC/USD", "source_type": "cex",
                  "chain_or_exchange": "kraken", "symbol_or_contract": "USDC/USD",
                  "contract_address": address.lower(), "first_seen": first_seen}, db)

    assert reconcile_assets(db, linked_at=first_seen) == [{
        "dex_canonical_id": f"ethereum:{address}", "cex_canonical_id": "kraken:USDC/USD",
        "linked_at": first_seen,
    }]
    assert [(row["dex_canonical_id"], row["cex_canonical_id"]) for row in read_lineage(db)] == [
        (f"ethereum:{address}", "kraken:USDC/USD")
    ]


def test_quality_checks_and_daily_run_summary(tmp_path):
    db = str(tmp_path / "pipeline.duckdb")
    from storage.db import connect, log_run_end, log_run_start, insert_event
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    upsert_asset({"canonical_id": "ethereum:0x1", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0x1",
                  "first_seen": timestamp}, db)
    insert_event({"canonical_id": "ethereum:0x1", "event_type": "new_pool_detected",
                  "timestamp": datetime(2024, 12, 31, tzinfo=timezone.utc),
                  "payload_json": {}, "source": "fixture"}, db)
    run_id = log_run_start("tier0_dex_poll:ethereum", db, started_at=timestamp, run_id="run-quality")
    log_run_end(run_id, "success", db, finished_at=timestamp, rows_written=3)

    report = data_quality_report(db, now=datetime(2025, 1, 2, tzinfo=timezone.utc))
    assert report["prelaunch_counts"]["events"] == 1
    assert report["duplicate_counts"]["lineage"] == 0
    assert report["null_counts"]["metadata"]["risk_flags_json"] == 0
    assert daily_ingestion_summary(db)[0]["rows_ingested"] == 3


def test_ambiguous_same_address_across_cex_assets_is_not_linked(tmp_path):
    db = str(tmp_path / "pipeline.duckdb")
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    address = "0xabc"
    upsert_asset({"canonical_id": "ethereum:0xabc", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": address,
                  "first_seen": timestamp}, db)
    for exchange in ("kraken", "coinbase"):
        upsert_asset({"canonical_id": f"{exchange}:ABC/USD", "source_type": "cex",
                      "chain_or_exchange": exchange, "symbol_or_contract": "ABC/USD",
                      "contract_address": address, "first_seen": timestamp}, db)
    assert reconcile_assets(db, linked_at=timestamp) == []


def test_reconcile_assets_leaves_missing_and_conflicting_identity_unlinked(tmp_path):
    db = str(tmp_path / "pipeline.duckdb")
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    upsert_asset({"canonical_id": "ethereum:missing", "source_type": "cex",
                  "chain_or_exchange": "kraken", "symbol_or_contract": "MISSING/USD",
                  "first_seen": timestamp}, db)
    upsert_asset({"canonical_id": "ethereum:conflict", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xabc",
                  "first_seen": timestamp}, db)
    for exchange in ("kraken", "coinbase"):
        upsert_asset({"canonical_id": f"{exchange}:ABC/USD", "source_type": "cex",
                      "chain_or_exchange": exchange, "symbol_or_contract": "ABC/USD",
                      "contract_address": "0xabc", "first_seen": timestamp}, db)

    assert reconcile_assets(db, linked_at=timestamp) == []


def test_data_quality_report_keeps_null_and_prelaunch_counts_explicit(tmp_path):
    db = str(tmp_path / "pipeline.duckdb")
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    upsert_asset({"canonical_id": "ethereum:missing", "source_type": "dex",
                  "chain_or_exchange": "ethereum", "symbol_or_contract": "0xmissing",
                  "first_seen": timestamp}, db)
    report = data_quality_report(db, now=timestamp)

    assert report["null_counts"]["assets"]["contract_address"] == 1
    assert report["duplicate_counts"]["assets"] == 0
    assert report["prelaunch_counts"] == {"ohlcv": 0, "events": 0, "metadata": 0}


def test_daily_ingestion_summary_excludes_failed_and_groups_job_source_exactly(tmp_path):
    db = str(tmp_path / "pipeline.duckdb")
    timestamp = datetime(2025, 1, 1, 12, tzinfo=timezone.utc)
    from storage.db import log_run_end, log_run_start

    successful = log_run_start("tier0_dex_poll:ethereum", db, started_at=timestamp, run_id="run-success")
    log_run_end(successful, "success", db, finished_at=timestamp, rows_written=3)
    failed = log_run_start("tier0_dex_poll:ethereum", db, started_at=timestamp, run_id="run-failed")
    log_run_end(failed, "failed", db, finished_at=timestamp, rows_written=99)

    assert daily_ingestion_summary(db) == [{
        "day": timestamp.date(), "source": "tier0_dex_poll",
        "job_name": "tier0_dex_poll:ethereum", "rows_ingested": 3,
    }]
