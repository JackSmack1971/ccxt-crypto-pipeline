# Repository architecture

This repository is a local ingestion and research pipeline. Phase 1 jobs fetch
external observations, normalize them at the ingestion boundary, and persist
them to DuckDB and Parquet. Phase 2 analysis consumes that local store read-only.

## Module boundaries and data flow

```text
External providers
  ├─ ccxt CEX markets/tickers/OHLCV ─────── ingestion/cex
  ├─ Tier 0 aggregator clients/poller ─────── ingestion/dex/tier0
  ├─ EVM RPC logs ────────────────────────── ingestion/evm/rpc.py
  ├─ EVM explorers/indexers ──────────────── ingestion/evm/providers.py
  └─ Helius Enhanced/DAS/RPC ─────────────── ingestion/solana
                                               │
                                               ▼
                              storage/db.py (single persistence boundary)
                                ├─ DuckDB: assets, ohlcv, events, metadata,
                                │          runs, lineage, schema_version
                                └─ Parquet: ohlcv/source=<source>/date=<UTC date>
                                               │
                         normalization/reconcile.py ── scheduler/status.py
                                               │
                                               ▼
                 analysis/datasets -> strategies -> backtesting -> runs/metrics
                                      └-> alpha -> reporting/claims -> charts/package
```

`scheduler/pipeline.py` invokes the one-pass ingestion functions, isolates job failures, and records structured run status. Its configured cadences are daily CEX refresh, 15–30 minute Tier 0 polling, one-minute listener polling, and nightly normalization. Provider-specific HTTP and RPC behavior stays in ingestion adapters.

## Canonical storage schema

`storage/schema.py` owns the idempotent DuckDB schema and `SCHEMA_VERSION = 5`. `storage/db.py` is the shared access layer.

| Table | Key/important fields | Meaning |
| --- | --- | --- |
| `assets` | `canonical_id` primary key; source, chain/exchange, symbol/contract, `contract_address` | Registered CEX and DEX assets |
| `ohlcv` | `(canonical_id, timestamp, timeframe, source)` primary key | Source-scoped OHLCV candles; `source` also drives Parquet partitioning |
| `events` | canonical ID, event type, timestamp, payload, source | New pools, trending pools, token mints, and pool creation |
| `metadata` | `(canonical_id, last_updated)` primary key | Timestamped holder, verification, deployer, LP and risk observations |
| `runs` | `run_id` primary key | Job start/end, status, row count, and error |
| `lineage` | `(dex_canonical_id, cex_canonical_id, linked_at)` primary key | Timestamped address-evidence links without replacing either identity |

Canonical IDs are `exchange:symbol` for CEX, `chain:contract_address` for EVM/DEX, and `solana:mint_address` for Solana. OHLCV writes use conflict updates and rewrite complete affected Parquet partitions, so replaying a backfill does not create duplicate logical rows.

## Provider separation and routing

EVM observation and enrichment are deliberately independent:

- Direct RPC URLs (`EVM_RPC_URL_*`) are used for latest blocks and factory log observation.
- Explorer/indexer adapters are used for historical/indexed enrichment through the normalized `EVMEnrichmentProvider` interface.
- A missing or unsupported free capability is represented as `UNSUPPORTED`/unavailable in metadata; there is no automatic paid-provider fallback.

| Chain | Chain ID | Enrichment adapter | Credential/config |
| --- | ---: | --- | --- |
| Ethereum | 1 | Etherscan V2 | `ETHERSCAN_API_KEY`; `chainid=1` |
| Arbitrum | 42161 | Etherscan V2 | same `ETHERSCAN_API_KEY`; `chainid=42161` |
| Base | 8453 | Routescan | optional `ROUTESCAN_API_KEY`; keyless mode is configured |
| BSC | 56 | BSCTrace/MegaNode | `MEGANODE_API_KEY`; endpoint must be configured |

Tier 0 remains the chain-agnostic fallback for configured networks. Its package contains Dexscreener, GeckoTerminal, and DefiLlama clients; the current normalized new-pool/trending-pool poll is backed by GeckoTerminal. Solana is separate from EVM and uses Helius Enhanced Transactions, DAS `getAsset`, and Solana RPC `getTokenLargestAccounts`; Solana risk screening is explicitly unsupported in the current adapter.

## Phase 1 freeze

Phase 1 ends at collection, normalization, quality reporting, scheduling, and
local persistence. Metadata and lineage observations are retained by observation
timestamp, so later readers can select only evidence known at a decision time. The
implemented Phase 2 slice adds read-only snapshots,
strategy intentions, next-bar simulation, metrics, and immutable run artifacts.
Phase 3 has a local, baseline-first cohort/feature/label/evaluation kernel and
file-based research artifacts. Phase 4 has a local claim/chart/static-package
kernel that accepts immutable approved manifests and leaves packages pending
human review. The Phase 1-to-Phase 3 persisted-data acceptance path and the
offline Phase 1-to-Phase 4 approved-handoff path are covered by fixture replay;
broader provider-observation completeness remains bounded by source availability.
No phase authorizes live trading or external publication.
