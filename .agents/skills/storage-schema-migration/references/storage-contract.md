# Phase 1 storage contract baseline

Use this file to recover the original storage-layer contract and non-negotiable test boundary. The repository's current authoritative schema may legitimately be newer after migrations; never downgrade it to this baseline.

## Canonical storage role

`/storage/` is the single persistence boundary used by later ingestion writers and future analysis readers. Storage is local DuckDB plus Parquet; this layer does not own provider/API behavior.

## Baseline tables

### `assets`

- `canonical_id` — primary key; `"exchange:symbol"` for CEX or `"chain:contract_address"` for DEX
- `source_type` — `cex` or `dex`
- `chain_or_exchange`
- `symbol_or_contract`
- `first_seen` — timestamp

### `ohlcv`

- `canonical_id`
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `timeframe`
- `source`

OHLCV is Parquet-backed and partitioned by `source` and date.

### `events`

- `canonical_id`
- `event_type` — baseline examples: `new_pool_detected`, `trending`, `liquidity_added`, `liquidity_removed`
- `timestamp`
- `payload_json`
- `source`

### `metadata`

- `canonical_id`
- `holder_count`
- `lp_locked` — boolean
- `contract_verified` — boolean
- `deployer_address`
- `risk_flags_json`
- `last_updated`

### `runs`

- `run_id`
- `job_name`
- `started_at`
- `finished_at`
- `status`
- `rows_written`
- `error_message` — nullable

Every ingestion job is expected to log a run here, but ingestion behavior itself is outside this skill.

## Baseline access layer

The original `storage/db.py` contract exposes:

- `upsert_asset`
- `insert_ohlcv_batch`
- `insert_event`
- `upsert_metadata`
- `log_run_start`
- `log_run_end`
- basic read helpers for each table

A migration must inspect these and any newer accessors rather than assuming this list is still exhaustive.

## Baseline invariants

- Keep one authoritative `SCHEMA_VERSION` constant and advance it for persisted-contract changes.
- Keep initialization idempotent.
- A storage-layer acceptance test must be able to create the DB from scratch, insert representative data, and read matching values back.
- Storage migration tests use fixture data only. No real external API calls belong in this layer.
