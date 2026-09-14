"""Phase 5 data-plane closure matrix (Slice 5.7).

Every guarantee exercised here already has dedicated per-slice fixture
coverage elsewhere (`tests/test_evm.py`, `tests/test_solana.py`,
`tests/test_storage.py`, `tests/test_scheduler.py`,
`tests/test_eligibility.py`, `tests/test_phase3.py`). This file adds no new
production behavior; it proves the Slice 5.1-5.6 guarantees compose in one
local dataset across two representative chains, offline, as required to
close Phase 5. See `docs/plans/phase-5-data-plane-closure-matrix.md`.
"""

from datetime import datetime, timedelta, timezone

import pytest

from analysis.alpha import CohortConfig, LabelDefinition, evaluate_chain_eligibility, extract_cohort, generate_labels
from analysis.datasets import DatasetPolicy, DatasetSnapshot
from ingestion.evm.listener import observe_once
from ingestion.solana.listener import run_once as solana_run_once
from storage.db import (get_ingestion_continuation, get_ingestion_cursor, insert_event,
                        insert_ohlcv_batch, provider_quality_summary, read_events,
                        record_provider_observation, repair_parquet_publication, upsert_asset,
                        upsert_reference_series_observation, verify_parquet_publication)


def _evm_block(number, block_hash, parent_hash):
    return {"hash": "0x" + block_hash * 32, "parentHash": "0x" + parent_hash * 32,
            "timestamp": "0x" + format(1735689600 + number, "x")}


def test_evm_cursor_restart_and_reorg_compose_and_gap_detection_fails_closed(tmp_path):
    """Representative EVM chain: Slice 5.1 restart + Slice 5.2 reorg reconciliation.

    Kept in its own store because a `chain_reorg_detected` audit event is not
    itself an asset-scoped research observation; loading it through
    `DatasetSnapshot.from_duckdb` is out of this slice's scope (see the
    closure matrix doc). The chain's resulting provider-quality outcome is
    what downstream eligibility gating in the composed dataset consumes.
    """
    hashes = {100: "aa", 101: "bb", 102: "ee"}

    class RPC:
        def get_block(self, number):
            return _evm_block(number, hashes[number], hashes.get(number - 1, "99"))
        def get_factory_logs(self, factories, from_block, to_block): return []

    db = str(tmp_path / "evm-closure.duckdb")
    chain = {"name": "ethereum", "chain_id": 1, "factories": []}
    assert observe_once(chain, RPC(), object(), object(), db_path=db,
                        from_block=100, to_block=101, cursor_source="evm_rpc") == 0
    insert_event({"canonical_id": "ethereum:0xpool", "event_type": "new_pool_detected",
                 "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc), "payload_json": {},
                 "source": "evm_rpc", "block_number": 100, "block_hash": "0x" + "aa" * 32}, db)
    hashes[100], hashes[101] = "cc", "dd"
    assert observe_once(chain, RPC(), object(), object(), db_path=db,
                        from_block=100, to_block=101, cursor_source="evm_rpc") == 0
    assert len([row for row in read_events(db) if row["event_type"] == "chain_reorg_detected"]) == 2
    assert not [row for row in read_events(db) if row["event_type"] == "new_pool_detected"]

    # Restart continues past the reorg boundary without skipping a block (5.1 + 5.2 compose).
    assert observe_once(chain, RPC(), object(), object(), db_path=db,
                        from_block=102, to_block=102, cursor_source="evm_rpc") == 0
    assert get_ingestion_cursor("evm_rpc", "ethereum", db)["position"] == 102

    # A gap in the requested range fails closed rather than silently skipping blocks.
    with pytest.raises(ValueError, match="skipped block range"):
        observe_once(chain, RPC(), object(), object(), db_path=db,
                     from_block=105, to_block=106, cursor_source="evm_rpc")
    assert get_ingestion_cursor("evm_rpc", "ethereum", db)["position"] == 102


def test_solana_gap_detection_fails_closed_without_advancing_progress(tmp_path):
    """Representative Solana chain: Slice 5.3 gap detection, isolated from the
    successful composed flow below so its recorded failure does not affect
    the eligibility evidence the composed dataset relies on."""
    class Client:
        def __init__(self): self.bootstrap = True
        def recent_transactions(self, address, *, limit, before=None):
            if self.bootstrap:
                self.bootstrap = False
                return [{"signature": "checkpoint", "timestamp": 1}]
            return [{"signature": "newest" if before is None else "still-not-checkpoint", "timestamp": 2}]
        def get_asset(self, address): return {}
        def largest_accounts(self, address): return []

    cfg = {"programs": {"token_metadata": "gap-program"},
           "discovery": {"limit": 1, "max_pages": 2, "transaction_types": ["TOKEN_MINT"]}}
    db = str(tmp_path / "solana-gap.duckdb")
    client = Client()
    assert solana_run_once(db_path=db, config=cfg, client=client) == 0
    with pytest.raises(RuntimeError, match="was not reached"):
        solana_run_once(db_path=db, config=cfg, client=client)
    assert get_ingestion_continuation("helius_enhanced", "gap-program", db)["token"] == "checkpoint"


def test_phase5_data_plane_closure_across_representative_evm_and_solana_chains(tmp_path, monkeypatch):
    """Compose Slices 5.1-5.6 in one local dataset spanning two representative
    chains: durable Solana resumability, provider quality/eligibility gating,
    DuckDB/Parquet recovery, and reference-series-backed forward-return
    labels, all read back through the real Phase 1 storage boundary with
    network access denied."""
    import socket
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("offline data-plane closure attempted network access")))

    db = str(tmp_path / "closure.duckdb")
    parquet_dir = tmp_path / "parquet"
    # Naive throughout (matching the Phase 3/4 fixture convention): DuckDB
    # round-trips timestamps as naive UTC, and `DatasetPolicy`/`Bar` comparisons
    # require both sides to agree.
    t0 = datetime(2025, 1, 1)

    # The ethereum chain's restart/reorg reconciliation is proven in isolation
    # above; here we record the same real outcome (a clean poll after
    # recovery) the way `scheduler.pipeline.Pipeline.evm_listeners` does.
    record_provider_observation("evm_rpc", "ethereum", "success", db, expected_interval_seconds=60.0)

    # --- Representative Solana chain: durable signature-paged resumable
    # discovery replays every intervening page without silent high-activity
    # loss (5.3), and its per-program outcome is recorded automatically (5.4).
    mint = "So11111111111111111111111111111111111111112"
    offsets = {"sig-5": 5, "sig-4": 4, "sig-3": 3, "sig-2": 2, "sig-1": 1, "sig-old": 0}

    class SolanaClient:
        def __init__(self):
            self.pages = {
                None: [{"signature": "sig-5"}, {"signature": "sig-4"}],
                "sig-4": [{"signature": "sig-3"}, {"signature": "sig-2"}],
                "sig-2": [{"signature": "sig-1"}, {"signature": "sig-old"}],
            }
            self.bootstrap = True

        def recent_transactions(self, address, *, limit, before=None):
            if self.bootstrap:
                self.bootstrap = False
                return [{"type": "TOKEN_MINT", "signature": "sig-old", "timestamp": 1735689600,
                        "events": {"tokenMint": mint}}]
            return [{**tx, "type": "TOKEN_MINT", "timestamp": 1735689600 + offsets[tx["signature"]],
                    "events": {"tokenMint": mint}} for tx in self.pages[before]]

        def get_asset(self, address): return {}
        def largest_accounts(self, address): return []

    solana_cfg = {"programs": {"token_metadata": "metadata-program"},
                 "discovery": {"limit": 2, "max_pages": 3, "transaction_types": ["TOKEN_MINT"]}}
    client = SolanaClient()
    assert solana_run_once(db_path=db, config=solana_cfg, client=client, expected_interval_seconds=60.0) == 1
    assert solana_run_once(db_path=db, config=solana_cfg, client=client, expected_interval_seconds=60.0) == 5
    assert get_ingestion_continuation("helius_enhanced", "metadata-program", db)["token"] == "sig-5"

    # --- Provider quality/eligibility gate composes over persisted history
    # (5.4): both chains observed here are eligible; a never-observed third
    # chain fails closed instead of defaulting to healthy.
    chain_eligibility = evaluate_chain_eligibility(
        provider_quality_summary(db),
        {"ethereum": [("evm_rpc", "ethereum")], "solana": [("helius_enhanced", "metadata-program")],
         "arbitrum": [("evm_rpc", "arbitrum")]},
    )
    assert chain_eligibility["ethereum"].eligible is True
    assert chain_eligibility["solana"].eligible is True
    assert chain_eligibility["arbitrum"].eligible is False
    assert chain_eligibility["arbitrum"].reason == "NO_PROVIDER_OBSERVATIONS"

    # --- Persist the cohort-eligible launches, OHLCV history, and
    # point-in-time ETH/USD and SOL/USD reference series (5.6) research needs.
    upsert_asset({"canonical_id": "ethereum:0xaaa", "source_type": "dex", "chain_or_exchange": "ethereum",
                 "symbol_or_contract": "0xaaa", "contract_address": "0xaaa", "first_seen": t0}, db)
    insert_event({"canonical_id": "ethereum:0xaaa", "event_type": "new_pool_detected", "timestamp": t0,
                 "payload_json": {"reserve_usd": 12_000, "token_address": "0xaaa"}, "source": "evm_rpc"}, db)
    # A distinct source from the listener's own "helius" launch events, since
    # `insert_event` is identity-deduplicated on (canonical_id, event_type,
    # timestamp, source) and the listener already recorded one at this time.
    insert_event({"canonical_id": f"solana:{mint}", "event_type": "token_mint_detected", "timestamp": t0,
                 "payload_json": {"reserve_usd": 15_000, "mint": mint}, "source": "helius-liquidity"}, db)

    for canonical_id, source in (("ethereum:0xaaa", "evm_rpc"), (f"solana:{mint}", "helius")):
        rows = [{"canonical_id": canonical_id, "timestamp": t0 + timedelta(hours=i),
                "open": 10 + i, "high": 10 + i, "low": 10 + i, "close": 10 + i,
                "volume": 1.0, "timeframe": "1h", "source": source} for i in range(2)]
        insert_ohlcv_batch(rows, db, parquet_dir=parquet_dir)

    for series_id, values in (("ETH/USD", (2_000.0, 2_200.0)), ("SOL/USD", (100.0, 110.0))):
        for hour, value in enumerate(values):
            upsert_reference_series_observation({"series_id": series_id, "observed_at": t0 + timedelta(hours=hour),
                                                 "value": value, "source": "persisted-reference"}, db)

    # --- A publication failure discovered after the fact does not lose data:
    # DuckDB stays authoritative and Parquet is mechanically recoverable (5.5).
    assert verify_parquet_publication(db, parquet_dir=parquet_dir) == []
    (parquet_dir / "source=evm_rpc" / "date=2025-01-01" / "part-00000.parquet").unlink()
    divergent = verify_parquet_publication(db, parquet_dir=parquet_dir)
    assert [(item["source"], item["status"]) for item in divergent] == [("evm_rpc", "missing")]
    repaired = repair_parquet_publication(db, parquet_dir=parquet_dir)
    assert [(item["source"], item["status"]) for item in repaired] == [("evm_rpc", "repaired")]
    assert verify_parquet_publication(db, parquet_dir=parquet_dir) == []

    # --- Research reads only the recovered, persisted local dataset: cohort
    # extraction respects the composed quality gate, and forward-return
    # labels for both representative chains derive from the persisted
    # reference series rather than an explicitly supplied observation.
    dataset = DatasetSnapshot.from_duckdb(
        db, DatasetPolicy(timeframe="1h", start=t0, end=t0 + timedelta(hours=1)), parquet_dir=parquet_dir)
    cohort_config = CohortConfig(t0, t0 + timedelta(days=1), chains=("ethereum", "solana"),
                                 chain_eligibility=chain_eligibility)
    cohort = extract_cohort(dataset, cohort_config)
    by_token_id = {row.token_id: row for row in cohort}
    assert by_token_id["ethereum:0xaaa"].chain == "ethereum" and by_token_id["ethereum:0xaaa"].analysis_eligible is True
    assert by_token_id[f"solana:{mint}"].chain == "solana" and by_token_id[f"solana:{mint}"].analysis_eligible is True
    # The listener's own launch events (real Helius transaction shape) carry no
    # address-identifying key the cohort address rule recognizes; they are
    # retained as an explicit unresolved exclusion rather than silently
    # collapsed onto the resolved token by canonical_id or symbol text.
    unresolved = by_token_id[f"unresolved:solana:{mint}"]
    assert unresolved.chain == "unknown" and unresolved.analysis_eligible is False

    labels = {label.token_id: label for label in generate_labels(
        dataset, cohort, LabelDefinition("return", "1h"),
        quote_assets={"ethereum:0xaaa": "ETH", f"solana:{mint}": "SOL"})}
    assert labels["ethereum:0xaaa"].status == "COMPLETE"
    assert labels["ethereum:0xaaa"].provenance["start_conversion"] == {
        "quote_asset": "ETH", "conversion_rate": 2_000.0, "conversion_source": "persisted-reference",
        "conversion_time": "2025-01-01T00:00:00", "conversion_policy": "phase3-quote-usd-v1",
    }
    assert labels[f"solana:{mint}"].status == "COMPLETE"
    assert labels[f"solana:{mint}"].provenance["end_conversion"]["conversion_rate"] == 110.0
    assert labels[f"solana:{mint}"].provenance["end_conversion"]["conversion_source"] == "persisted-reference"
