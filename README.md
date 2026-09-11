# ccxt-crypto-pipeline

`ccxt-crypto-pipeline` is a local crypto research pipeline. Phase 1 collects,
normalizes, and persists CEX and DEX/on-chain observations; the implemented
Phase 2 slice provides deterministic, offline backtesting over those snapshots.

Ingestion remains the only provider-facing layer. Phase 2 analysis reads local
persisted data and never calls live providers.

## Contents

- [Quickstart](#quickstart)
- [Features](#features)
- [Architecture](#architecture)
- [Usage](#usage)
- [Configuration](#configuration)
- [Testing & Verification](#testing--verification)
- [Troubleshooting](#troubleshooting)
- [Stack Inventory](#stack-inventory)
- [Reproducibility & Maintenance](#reproducibility--maintenance)
- [Contributing](#contributing)
- [Governance](#governance)
- [Roadmap](#roadmap)
- [License](#license)

## Quickstart

### Prerequisites

- Python 3.10 or newer
- Network access for live CEX, aggregator, RPC, explorer, and Solana provider calls
- Credentials and RPC URLs for the providers you intend to use; see [`.env.example`](.env.example)

### Install

```powershell
python -m pip install -e .
```

Pinned dependencies are declared in [`pyproject.toml`](pyproject.toml) and locked in [`uv.lock`](uv.lock).

### Configure

Copy `.env.example` to a local `.env` and fill only the credentials required by the enabled paths. Keep `.env` untracked. Runtime behavior is configured in [`config/`](config/); details are in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

### Run

```powershell
python -m storage storage/pipeline.duckdb
python -m scheduler --once
```

Run the required CEX backfill example:

```powershell
python -m ingestion.cex.backfill --exchange kraken --symbol BTC/USDT --timeframe 1d --since 2023-01-01
```

For continuous scheduling, use `python -m scheduler`.

### Verify

```powershell
python -m scheduler.status
python -m normalization.reconcile --db storage/pipeline.duckdb --report
```

The status command prints JSON derived from the `runs` table. A live cycle can skip EVM/Solana work when corresponding environment values are absent; provider failures are recorded in `runs`.

## Features

- CEX universe discovery, since-paginated OHLCV backfill, resumable checkpoints, incremental refresh, ticker snapshots, rate limiting, and transient-error backoff through `ccxt`.
- Chain-agnostic Tier 0 provider clients and GeckoTerminal-backed new-pool/trending-pool polling.
- Shared EVM factory-log observation for Ethereum, Base, Arbitrum, and BSC, separated from explorer/indexer enrichment.
- Solana Tier 2 launch discovery and metadata/holder collection through Helius.
- Canonical DuckDB persistence with Parquet OHLCV partitions and idempotent writes.
- Contract-address-based DEX↔CEX lineage reconciliation, data-quality reporting, and structured scheduler health.

## Architecture

```text
ccxt CEX adapters ------------------------> ingestion/cex -------+
Dexscreener, GeckoTerminal, DefiLlama ---> ingestion/dex/tier0 -+
EVM RPC endpoints ------------------------> ingestion/evm -------+--> DuckDB and OHLCV Parquet
Etherscan V2, Routescan, MegaNode --------> ingestion/evm -------+
Helius Enhanced, DAS, RPC ----------------> ingestion/solana ---+

DuckDB and OHLCV Parquet --> normalization
DuckDB and OHLCV Parquet --> scheduler and status
```

The scheduler coordinates existing jobs and records each job in `runs`; it does not contain provider-specific request logic. `ingestion/evm/rpc.py` observes blocks and factory logs. `ingestion/evm/providers.py` implements the normalized enrichment interface. Unsupported capabilities remain explicit rather than being fabricated or silently routed to a paid fallback. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the final data flow, schema, and routing table.

## Directory structure

```text
config/                 YAML runtime settings and provider routing
ingestion/cex/          CEX discovery, backfill, refresh
ingestion/dex/tier0/    Aggregator clients, throttling, polling
ingestion/evm/          Shared RPC observation and enrichment adapters
ingestion/solana/       Solana-specific Helius ingestion
normalization/          Identity reconciliation and data-quality reports
scheduler/              One-shot/continuous orchestration and health CLI
storage/                Canonical schema and DuckDB/Parquet access
tests/                  Fixture/unit coverage for implemented paths
docs/                   Architecture and local operations documentation
```

## Usage

| Command | Purpose |
| --- | --- |
| `python -m storage PATH_TO_DATABASE` | Initialize canonical storage |
| `python -m ingestion.cex.backfill ...` | Backfill one CEX symbol/timeframe |
| `python -m ingestion.cex.refresh` | Refresh configured CEX assets |
| `python -m ingestion.dex.tier0.poller` | Run one Tier 0 poll |
| `python -m ingestion.solana.listener` | Run one Solana pass |
| `python -m normalization.reconcile --report` | Reconcile and print quality summaries |
| `python -m scheduler --once` | Run all stages once and exit |
| `python -m scheduler.status` | Print JSON health status |

## Configuration

Safe examples are provided in [`.env.example`](.env.example). YAML settings live in `config/cex.yaml`, `config/chains.yaml`, `config/evm.yaml`, and `config/solana.yaml`. The complete variable and credential setup is in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Developer Command Center

| Command | Category | Purpose |
| --- | --- | --- |
| `python -m scheduler --once` | Operations | Run one complete pipeline cycle |
| `python -m scheduler` | Operations | Start continuous scheduling |
| `python -m scheduler.status` | Monitoring | Print machine-readable health |
| `python -m normalization.reconcile --report` | Data quality | Print lineage and quality summaries |
| `python -m pytest` | Verification | Run fixture/unit tests |

## Testing & Verification

The repository contains pytest tests under `tests/`. Run them with `python -m pytest`. If the host interpreter lacks project dependencies, use `./scripts/run-tests`; it selects the already-provisioned `.venv` dependencies without retrieving packages. Fixture tests do not prove live provider acceptance; use the live-check prerequisites in [`docs/RUNBOOK.md`](docs/RUNBOOK.md) and inspect stored rows and `scheduler.status`.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `HELIUS_API_KEY is required` | Solana credential is absent | Set `HELIUS_API_KEY`, or treat Solana as intentionally skipped |
| EVM listener reports RPC URL failure | Chain RPC variable is empty or invalid | Set the matching `EVM_RPC_URL_*`; explorer keys do not replace RPC URLs |
| BSC enrichment is `UNSUPPORTED` | MegaNode endpoint is unconfigured | Configure a documented free endpoint and `MEGANODE_API_KEY` |
| Status is unhealthy | A job is `failed` or `running` in `runs` | Inspect status and the latest error, correct configuration, and retry |
| Backfill repeats old candles | A different database/config path was used | Confirm the DuckDB and Parquet paths in `config/cex.yaml` |

## Stack Inventory

| Layer | Technology | Version |
| --- | --- | --- |
| Runtime | Python | `>=3.10` |
| CEX API | ccxt | `4.5.10` |
| Storage | DuckDB | `1.5.5` |
| Columnar files | PyArrow | `25.0.1` |
| Data handling | pandas | `2.3.3` |
| HTTP | requests | `2.32.5` |
| Configuration | PyYAML | `6.0.2` |
| Scheduling | APScheduler | `3.11.0` |

Versions are from [`pyproject.toml`](pyproject.toml).

## Reproducibility & Maintenance

Use the pinned project manifest and [`uv.lock`](uv.lock) for repeatable dependency resolution. Local `.env`, DuckDB, Parquet, virtual-environment, and Python cache artifacts are intended to remain untracked. Inspect [`docs/RUNBOOK.md`](docs/RUNBOOK.md) before removing local persisted data.

## Governance

| Area | Status |
| --- | --- |
| Contribution guidelines | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Security policy | [`SECURITY.md`](SECURITY.md) |
| Code of conduct | No `CODE_OF_CONDUCT.md` found |
| License | No license file found |
| Support | [`SUPPORT.md`](SUPPORT.md) and GitHub Issues |

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening an issue or pull request. It documents the repository’s phase boundaries, offline verification requirements, storage migration rules, provider integration constraints, and review expectations. See [`SECURITY.md`](SECURITY.md) for private vulnerability reporting and secret-handling rules.

## Roadmap

The canonical forward execution roadmap is [`ROADMAP.md`](ROADMAP.md). It records the current phase frontier, dependency-ordered implementation slices, per-slice acceptance gates, phase exit criteria, deferred boundaries, and the maintenance contract agents must follow as work lands.

The current frontier is Phase 4 completion and integrity reconciliation. Phase 1–4 kernels are implemented, but the roadmap intentionally keeps Phase 4 open until the remaining statistical-governance, real-data observation, quote-currency, identity, metrics, claim-derivation, and continuous-verification gaps are closed with executable evidence.

## License

No license file was found. Add a license before publishing or accepting contributions.

## Phase boundary

Ingestion is the only layer allowed to call external providers. Analysis reads
persisted local data and remains offline-capable; it does not authorize live or
paper trading, automated execution, alpha claims, or external publication.
