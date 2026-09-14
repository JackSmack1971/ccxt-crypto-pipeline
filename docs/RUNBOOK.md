# Phase 1 local runbook

All commands below run from the repository root. The pipeline writes to local DuckDB and Parquet; it does not require hosted infrastructure.

## Setup

1. Install Python 3.10+.
2. Install the pinned project:

   ```powershell
   python -m pip install -e .
   ```

3. Copy `.env.example` to `.env` and fill the provider values required for the jobs you will run. Never commit `.env`.
4. Review the YAML defaults in `config/`.
5. Initialize storage:

   ```powershell
   python -m storage storage/pipeline.duckdb
   ```

Initialization is idempotent and creates the canonical schema. The default CEX config uses `storage/pipeline.duckdb` and `storage/parquet`.

## Environment contract

| Variable | Used by | Required when | Secret? |
| --- | --- | --- | --- |
| `ETHERSCAN_API_KEY` | Etherscan V2 | Ethereum or Arbitrum enrichment | Yes |
| `ROUTESCAN_API_KEY` | Routescan | Keyed Base requests; keyless access is allowed by config | Yes |
| `MEGANODE_API_KEY` | BSCTrace/MegaNode | BSC enrichment when an endpoint is configured | Yes |
| `HELIUS_API_KEY` | Helius | Solana listener | Yes |
| `EVM_RPC_URL_ETHEREUM` | Ethereum RPC listener | Ethereum observation | May contain credentials; treat as secret |
| `EVM_RPC_URL_BASE` | Base RPC listener | Base observation | May contain credentials; treat as secret |
| `EVM_RPC_URL_ARBITRUM` | Arbitrum RPC listener | Arbitrum observation | May contain credentials; treat as secret |
| `EVM_RPC_URL_BSC` | BSC RPC listener | BSC observation | May contain credentials; treat as secret |

RPC URLs and explorer credentials are independent. Setting an explorer API key does not provide RPC observation, and setting an RPC URL does not provide explorer enrichment.

## Provider setup

- Ethereum and Arbitrum use Etherscan V2 with the shared `ETHERSCAN_API_KEY`; the adapter sends the chain-specific chain ID.
- Base uses Routescan. `ROUTESCAN_API_KEY` is optional because `config/evm.yaml` explicitly permits keyless access with throttling. Contract verification and deployer lookup remain unsupported in this adapter.
- BSC is routed to `bsctrace_meganode`. The checked-in configuration leaves its deployment-specific `base_url` empty, so enrichment reports unsupported until a documented free endpoint and `MEGANODE_API_KEY` are supplied. It is never redirected to Etherscan.
- Solana uses Helius Enhanced Transactions, DAS, and RPC with `HELIUS_API_KEY`. The listener covers configured Token Metadata, Raydium, Orca, and pump.fun program addresses. Risk screening is recorded as unsupported.
- Tier 0 uses public aggregator endpoints and configuration-driven network mappings. Throttles and retry behavior are implemented in the provider clients.

## Run operations

### CEX backfill

```powershell
python -m ingestion.cex.backfill --exchange kraken --symbol BTC/USDT --timeframe 1d --since 2023-01-01
```

The backfill uses `since` pagination, resumes after the stored checkpoint, and writes OHLCV to DuckDB plus `source`/UTC-date Parquet partitions. Re-running the same command is idempotent.

### One-pass jobs

```powershell
python -m ingestion.cex.universe
python -m ingestion.cex.refresh
python -m ingestion.dex.tier0.poller
python -m ingestion.solana.listener
python -m normalization.reconcile --report
```

EVM observation is normally invoked by the scheduler after its chain RPC variables are configured.

### Scheduler

Run and exit after one complete cycle:

```powershell
python -m scheduler --once
```

Run continuously:

```powershell
python -m scheduler
```

The initial cycle runs CEX refresh, Tier 0 polling, EVM listeners, Solana listener, and normalization. Continuous scheduling then uses daily CEX refresh, a configured 15–30 minute Tier 0 interval (default 20), one-minute listener intervals, and normalization at 02:00 UTC.

## Monitor

```powershell
python -m scheduler.status
```

The JSON report includes `healthy`, status counts, total runs, and the latest run for every job. `healthy` is false if any run is `failed` or still `running`. Inspect the `runs` table directly when needed:

```powershell
python -c "import duckdb; c=duckdb.connect('storage/pipeline.duckdb'); print(c.sql('select * from runs order by started_at desc limit 20'))"
```

For normalization and data-quality checks:

```powershell
python -m normalization.reconcile --db storage/pipeline.duckdb --report
```

That report covers nulls, logical duplicates, future timestamps, pre-launch timestamps, lineage, and daily successful row summaries.

## Debugging

1. Run `python -m scheduler.status` and identify the latest failed job and `error_message`.
2. Confirm the job’s YAML path and database path are the ones you intended.
3. Confirm required environment variables without printing their values. RPC URLs and API keys must not be logged.
4. Retry the smallest one-pass command for the failing boundary.
5. Check provider rate limits, HTTP authentication, and transient availability. Adapters retry transient failures and preserve explicit unsupported states.
6. If storage looks inconsistent, run the normalization report and inspect the relevant DuckDB rows plus the affected `storage/parquet/source=.../date=...` partition.
7. If OHLCV Parquet looks stale or missing relative to DuckDB (for example after a disk-full or permission error during ingestion), run `python -m storage storage/pipeline.duckdb --verify-parquet` and then `--repair-parquet` (see [Verification boundaries](#verification-boundaries) below) instead of re-running ingestion.

| Error/symptom | Action |
| --- | --- |
| `HELIUS_API_KEY is required` | Set the key or accept that Solana is skipped by the scheduler. |
| RPC URL missing/invalid | Set the matching `EVM_RPC_URL_*`; provider credentials are not substitutes. |
| BSC capabilities unsupported | Configure the documented free MegaNode endpoint; no paid fallback is used. |
| `healthy: false` | Read the latest `runs.error_message`, correct the boundary configuration, and rerun the isolated job. |
| No CEX assets | Check exchange IDs, spot-market availability, ticker volume, and `minimum_24h_quote_volume` in `config/cex.yaml`. |
| OHLCV Parquet partition missing/stale after a publication failure | Run `python -m storage <db> --verify-parquet` then `--repair-parquet`; DuckDB already holds the authoritative rows. |

## Verification boundaries

Run fixture/unit tests with:

```powershell
python -m pytest
```

These tests do not establish live-provider acceptance. A real acceptance check must have the necessary credentials/network access and must be reported separately from fixture evidence. Never claim a live integration passed when the external prerequisite was unavailable.

DuckDB is the canonical OHLCV store; Parquet is a reproducible read cache for
analysis snapshots. OHLCV writes stage Parquet files and commit the DuckDB
transaction before publishing the staged files. This local two-store boundary
cannot provide a cross-filesystem atomic commit, so a filesystem publication
failure after the DuckDB commit can leave a partition's Parquet file missing
or stale relative to DuckDB.

DuckDB remains authoritative in that state; recover mechanically instead of
re-running ingestion:

```powershell
python -m storage storage/pipeline.duckdb --verify-parquet
python -m storage storage/pipeline.duckdb --repair-parquet
```

`--verify-parquet` reports every `(source, date)` OHLCV partition whose
Parquet file is missing, unreadable, or does not match DuckDB, without
changing anything. `--repair-parquet` deterministically rebuilds only the
diverging partitions from DuckDB using the same stage-then-atomic-replace
sequence normal ingestion uses, and is idempotent: running it again against
an already-repaired store reports nothing to repair. Pass `--parquet-dir` if
the store does not use the default `<database directory>/parquet` layout.

## Data safety and phase boundaries

Do not delete `storage/pipeline.duckdb` or `storage/parquet` while jobs are running. They are local persisted state and can be recreated, but deletion removes collected data. The Phase 2 and Phase 3 analysis slices read these persisted inputs locally and must not call providers. Phase 4 consumes approved local research artifacts and emits pending review packages; it does not publish externally. No phase authorizes live or paper trading, automated execution, or external publication.
