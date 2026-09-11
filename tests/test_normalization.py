from datetime import datetime, timezone

from normalization.reconcile import data_quality_report, daily_ingestion_summary, reconcile_assets
from storage.db import read_lineage, upsert_asset


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
