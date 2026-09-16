# ccxt-crypto-pipeline

`ccxt-crypto-pipeline` is a local-first, reproducible crypto quantitative
research system for point-in-time data, governed experimentation, validation,
and evidence-bound research reporting. It helps a researcher move from
external CEX/DEX/on-chain observations to canonical local datasets,
deterministic backtests, hypothesis evaluation, robustness evidence, and
reviewable research packages without hiding uncertainty or provenance.

The implemented product has four deliberately separated surfaces: ingestion
collects provider observations; analysis builds point-in-time datasets and
research results; governed experiments and validation test those results for
leakage, instability, practical effect, and negative controls; reporting binds
claims and charts to immutable evidence and produces deterministic local
packages for human review/export.

This is research software, not a trading system. Ingestion is the only layer
that performs provider/network I/O. Analysis and reporting operate on
persisted local data or approved local artifacts. Human approval does not
promote a candidate into execution, and export prepares a bundle for manual
publication rather than posting it. Paper/forward execution (Phase 9) and
live execution (Phase 10) are separately gated and remain deferred.

Determinism and evidence boundaries matter because a result that cannot be
replayed from point-in-time inputs, declared methodology, and immutable
artifacts cannot support an honest research conclusion. Tests and fixture
success do not establish provider completeness, profitability, predictive
alpha, or execution readiness.

## Current frontier

Phase 8 research product and publication operations are complete. The active
frontier is **Phase 8R Empirical Research Readiness**, focused on dataset-
quality evidence, scientific benchmarks, durable question/hypothesis identity,
falsification, research campaigns, and independent methodological review. See
the authoritative [roadmap](ROADMAP.md) for status and acceptance criteria.

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
- A local governed-experiment interface that validates declarative specs, runs
  them against read-only persisted snapshots, verifies immutable results, and
  records separate human approval attestations and immutable review history.
- Optional, explicitly configured purged walk-forward folds with expanding
  training windows, non-overlapping validation windows, and a sealed holdout.

## Architecture

```text
external observations --> ingestion --> canonical DuckDB / Parquet
                                      |
                                      v
                 normalization / point-in-time datasets
                                      |
                                      v
       backtesting / hypothesis research / governed experiments
                                      |
                                      v
          validation / falsification / robustness evidence
                                      |
                                      v
        immutable artifacts --> deterministic reporting
                                      |
                                      v
                         human review / manual export
```

The scheduler coordinates ingestion and normalization jobs and records each job
in `runs`; it does not contain provider-specific request logic. The analysis
boundary is read-only and point-in-time. Unsupported capabilities remain
explicit rather than being fabricated or silently routed to a paid fallback.
See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the current data flow,
schema, routing table, and research/reporting boundaries.

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
| `python -m storage PATH_TO_DATABASE --verify-parquet` | Report OHLCV Parquet partitions that diverge from DuckDB |
| `python -m storage PATH_TO_DATABASE --repair-parquet` | Deterministically rebuild diverging OHLCV Parquet partitions from DuckDB |
| `python -m ingestion.cex.backfill ...` | Backfill one CEX symbol/timeframe |
| `python -m ingestion.cex.refresh` | Refresh configured CEX assets |
| `python -m ingestion.dex.tier0.poller` | Run one Tier 0 poll |
| `python -m ingestion.solana.listener` | Run one Solana pass |
| `python -m normalization.reconcile --report` | Reconcile and print quality summaries |
| `python -m analysis.experiments validate SPEC.json` | Validate and content-identify a governed experiment spec |
| `python -m analysis.experiments validate-question QUESTION.json` | Validate and identify a durable research question declaration |
| `python -m analysis.experiments validate-hypothesis HYPOTHESIS.json` | Validate and identify a durable hypothesis declaration |
| `python -m analysis.experiments write-registry REGISTRY.json --output REGISTRIES` | Write an immutable question/hypothesis registry |
| `python -m analysis.experiments validate-campaign CAMPAIGN.json` | Validate and identify a research campaign declaration |
| `python -m analysis.experiments write-campaign CAMPAIGN.json --output CAMPAIGNS` | Write an immutable research campaign |
| `python -m analysis.experiments inspect-campaign CAMPAIGN_DIR` | Verify and inspect an immutable research campaign |
| `python -m analysis.experiments run SPEC.json --db DB --output RUNS [--timeframe 1h] [--source SOURCE]` | Execute the canonical experiment runner against a read-only local snapshot |
| `python -m analysis.experiments inspect RUN_DIR` | Hash-verify and inspect one immutable experiment run |
| `python -m analysis.experiments approve RUN_DIR --approval-dir APPROVALS --reviewer NAME --reviewed-at ISO_TIME --rationale TEXT` | Record a separate, immutable human approval attestation |
| `python -m analysis.datasets DATABASE --output PROFILES [--timeframe 1h] [--source SOURCE]` | Build and immutably write deterministic dataset-quality/coverage evidence |
| `python -m analysis.benchmarks` | Print the deterministic offline scientific benchmark corpus and identity |
| `python -m reporting.package record TARGET --target-kind research_run\|package --history-dir HISTORY --decision approved\|rejected\|superseded\|note --reviewer NAME --reviewed-at ISO_TIME` | Record an immutable review decision bound to an exact research run or report package |
| `python -m reporting.package show TARGET_ID --history-dir HISTORY` | Verify and list review history deterministically |
| `python -m reporting.package catalog --research-root RUNS --package-root PACKAGES [--history-dir HISTORY] [--query TEXT]` | Verify, list, and search immutable research runs and report packages locally |
| `python -m reporting.package export --package PACKAGE --history-dir HISTORY --output-root EXPORTS` | Export an approved, immutable package for manual human publication preparation |
| `python -m scheduler --once` | Run all stages once and exit |
| `python -m scheduler.status` | Print JSON health status |

The experiment interface is local and emits JSON. `run` never contacts a
provider; select the persisted bar timeframe and, when needed, one unambiguous
source with repeatable `--source` options. `approve` first verifies every run
artifact and writes outside the immutable run directory. Approval attests to
human review only: it does not change the candidate's promotion state, unseal a
holdout, authorize trading, or publish a result.

Research declarations are separate from experiment results. A question records
the intended inquiry, a hypothesis records one testable claim, and a registry
can bind that hypothesis to an experiment spec. Binding makes the question and
hypothesis identities part of the spec and run identities, so a result cannot
silently change what was declared. Declarations retain unavailable or
question-specific evidence as explicit fields; they do not establish alpha or
execution readiness.

A research campaign binds a question, registry, exact dataset/profile identities,
hypothesis outcomes, experiment/run identities, artifact identities, conclusion,
and limitations into one immutable provenance object. Campaign validation is
local and replayable; rejected hypotheses remain part of the record, and a
campaign is research evidence only, not an execution authorization.

Use `execute_campaign(...)` to run bound experiment specs against a persisted
`DatasetSnapshot`, verify the resulting run artifacts and dataset profile, and
write one immutable campaign. A promoted outcome is accepted only when its run
has holdout confirmation and a passing validation closure; rejected outcomes
remain valid research results.

Experiment runs also emit deterministic `uncertainty.json` evidence using the
configured moving-block bootstrap policy. The policy records its method,
dependence structure, resample count, block size, and seed; unsupported
dependence structures fail validation and unavailable observations remain
explicit rather than being imputed.

Experiment specs select evaluation behavior through `split.evaluation_mode`.
The default `single_split` preserves the chronological discovery/validation/
holdout contract. Set it to `walk_forward` and declare `walk_forward_folds`
(at least two) to emit a hash-bound `walk_forward.json` artifact. Every fold
records its training and validation membership plus purge/embargo removals;
the final 20 percent remains sealed and is never included in a fold.

Promotion also requires a declared practical-effect floor
(`promotion_policy.minimum_effect_size`) and records the measured
candidate-vs-baseline effect in its evidence. Statistical uncertainty and
practical effect are separate gates: a statistically supported result below
the effect floor is rejected, while missing effect evidence remains
unavailable.

Runs also emit `stress_matrix.json`, a deterministic Cartesian matrix of the
spec's approved fee, slippage, minimum-liquidity, and missingness scenarios.
The matrix reuses the discovery-selected token ids, keeps incomplete evidence
explicit, and never reselects a candidate from validation or sealed holdout
rows. Change the declarative `stress` policy in a spec to change its
content-addressed methodology identity.

Runs also emit `stability.json`, discovery-only evidence for the selected
candidate's concentration by chain, fixed-length era, launch-liquidity band,
provider, and leave-one-out launch. The declared `stability` policy controls
these dimensions and the dominance threshold; missing or empty evidence stays
explicit and the analysis never reselects a candidate from validation or holdout.

Runs also emit `negative_controls.json`, using the fixed discovery selection
with deterministic label permutations and a declared known-null control.
Controls are synthetic evidence for leakage and false-positive detection; they
never change candidate selection or promotion and never use sealed holdout rows.

Runs also emit `validation_closure.json`, which records whether the fixed
discovery selection is eligible for closure and whether its configured
uncertainty, stress, stability, and negative-control evidence all pass after
holdout confirmation; configured walk-forward evidence is included as well. A
passing closure is replayable research evidence, not a profitability claim or
authorization to trade.

Runs also emit `falsification.json`. Its versioned policy is part of the
experiment identity and requires every declared falsification method to have
passed, failed, or explicitly unavailable evidence. Unsupported tests remain
unavailable; results cannot be selected post-hoc from an undeclared menu.

Review history is stored separately from immutable research runs and report
packages. Each record is content-addressed and linked to the target's exact
manifest hash; supported decisions are `approved`, `rejected`, `superseded`,
and reviewer `note`. Supersession must reference an existing review for the
same target. Review history does not publish packages or change research
promotion state.

Approved handoffs generate immutable, pending-review packages containing the
Markdown article source, a self-contained accessible `article.html` draft with
inline validated SVG charts, chart specifications, the claim ledger, and
methodology/limitations. The HTML renderer is deterministic and offline; its
renderer and output-format identities are recorded in `package-manifest.json`.

Optional assisted drafts can be generated from a package's validated claim ledger
with `reporting.package.generate_assisted_draft`. The caller supplies the model
function and model identifier; the isolated suggestion rejects numbers and
comparisons, never changes the deterministic article, and remains pending review.

An export requires a verified package with a current, unsuperseded effective
approval and no later effective rejection in its immutable review history. It
copies only deterministic publication artifacts into a self-verifying local
bundle; it does not post, upload, contact a network, or record publication, and
it makes no profitability or alpha claim.

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

The repository contains pytest tests under `tests/`. Run them with the project interpreter: on PowerShell use `./scripts/run-tests.ps1`, and on POSIX shells use `./scripts/run-tests`. These entry points select the already-provisioned `.venv` dependencies instead of a host interpreter that may not have `duckdb` or `APScheduler`. Provision the environment first with `uv sync --locked` if needed. Fixture tests do not prove live provider acceptance; use the live-check prerequisites in [`docs/RUNBOOK.md`](docs/RUNBOOK.md) and inspect stored rows and `scheduler.status`.

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

Phase 8 research product and publication operations are complete, including
deterministic report output, local catalog/navigation, review history, and
human-gated publication export. Phase 8R empirical research readiness is the
active frontier. Phase 9 paper/forward execution and Phase 10 live execution
remain deferred pending separate product and safety decisions.

## License

No license file was found. Add a license before publishing or accepting contributions.

## Phase boundary

Ingestion is the only layer allowed to call external providers. Analysis reads
persisted local data and remains offline-capable; research evidence does not
authorize trading, human approval does not promote a candidate into execution,
and publication/export remains human-gated. No phase currently authorizes
paper/forward execution, live execution, automated execution, alpha claims, or
external publication.
