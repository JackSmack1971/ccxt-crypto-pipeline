# Repository architecture

This repository is a local-first crypto quantitative research system. Ingestion
collects and normalizes external observations; downstream analysis, governed
experiments, validation, and reporting consume persisted local data or approved
immutable artifacts. The architecture preserves point-in-time semantics and
keeps execution outside the current product boundary.

## Module boundaries and data flow

```text
external observations
        │
        ▼
ingestion (CEX, Tier-0 DEX, EVM, Solana; only network-I/O boundary)
        │
        ▼
canonical DuckDB + derived OHLCV Parquet
        │
        ▼
normalization / point-in-time datasets
        │
        ▼
backtesting / hypothesis research / governed experiments
        │
        ▼
validation / falsification / robustness evidence
        │
        ▼
immutable experiment and report artifacts
        │
        ▼
deterministic reporting → human review → manual publication export
```

`scheduler/pipeline.py` invokes the one-pass ingestion functions, isolates job failures, and records structured run status. Its configured cadences are daily CEX refresh, 15–30 minute Tier 0 polling, one-minute listener polling, and nightly normalization. Provider-specific HTTP and RPC behavior stays in ingestion adapters.

## Canonical storage schema

`storage/schema.py` owns the idempotent DuckDB schema and
`SCHEMA_VERSION = 13`; `storage/db.py` is the shared access layer. DuckDB is
canonical persistence and Parquet is derived publication/cache state.

| Table | Key/important fields | Meaning |
| --- | --- | --- |
| `assets` | `canonical_id` primary key; source, chain/exchange, symbol/contract, `contract_address` | Registered CEX and DEX assets |
| `ohlcv` | `(canonical_id, timestamp, timeframe, source)` primary key | Source-scoped OHLCV candles; `source` also drives Parquet partitioning |
| `events` | canonical ID, event type, timestamp, payload, source | New pools, trending pools, token mints, and pool creation |
| `metadata` | `(canonical_id, last_updated)` primary key | Timestamped holder, verification, deployer, LP and risk observations |
| `runs` | `run_id` primary key | Job start/end, status, row count, and error |
| `lineage` | `(dex_canonical_id, cex_canonical_id, linked_at)` primary key | Timestamped address-evidence links without replacing either identity |
| `asset_relationships` | market ID, constituent asset ID, role, venue, observation time, source | Point-in-time pool/market constituent identity without symbol inference |
| `dex_price_observations`, `price_observations` | source-scoped price/liquidity observations | Short-horizon DEX and on-chain observations |
| `observation_capabilities` | source/capability/status | Explicit supported, unavailable, or unsupported evidence |
| `ingestion_cursors`, `ingestion_continuations` | provider/scope cursor state | Resumable ingestion progress |
| `evm_block_observations`, `provider_observation_log` | block/provider status and evidence | Reorg-aware and provider-quality observations |
| `reference_series` | timestamped reference values | Historical/reference-series-backed conversion evidence |

Canonical IDs are `exchange:symbol` for CEX and address-scoped `chain:address`
identities for DEX markets and tokens. A market and a token therefore remain
distinct even when upstream payloads use a generic address field; the
`asset_relationships` rows identify base/quote or ordered constituents and the
time that relationship became visible. OHLCV writes use conflict updates and
rewrite complete affected Parquet partitions, so replaying a backfill does not
create duplicate logical rows.

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

## Research and reporting boundaries

Phase 1 provides collection, normalization, quality reporting, scheduling, and
local persistence. Phases 2–3 provide read-only point-in-time snapshots,
deterministic backtesting, cohort/feature/label evaluation, governed candidate
promotion, and immutable research runs. Phase 4 reporting validates claims,
derivations, charts, and approved handoffs into deterministic packages. Phases
6–7 add governed experiment identity, frozen hypothesis families, uncertainty,
practical effect, stress, stability, negative controls, and validation closure.
Phase 8 adds immutable review history, catalog/navigation, and human-gated local
publication export. Phase 8R adds empirical research-readiness evidence
(dataset-quality profiles, a scientific benchmark corpus, durable question/
hypothesis identity, falsification, research campaigns, and independent
methodological review) and is complete; Phase 9/10 activation decisions are
governed by `ROADMAP.md`.

Analysis consumes persisted local data and reporting consumes approved local
artifacts; neither calls providers or changes canonical ingestion rows.
Research evidence and human approval do not authorize trading or candidate
execution. Export prepares a local bundle for manual publication preparation;
paper/forward execution (Phase 9) and live execution (Phase 10) remain
separately gated and deferred. Fixture/test success does not prove provider
completeness or profitability.
