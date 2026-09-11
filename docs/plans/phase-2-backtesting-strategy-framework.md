# Phase 2 design pass: backtesting and strategy framework

**Status:** Implemented first slice; strategy expansion remains deferred
**Date:** 2026-09-09
**Depends on:** Phase 1 local DuckDB + Parquet ingestion contract

## Goal

Provide a reproducible, event-aware research runtime that can answer: “Given only
observations available at time `t`, what would this strategy have done, and what
were the resulting costs and returns?” The framework must support a small first
strategy end to end without becoming a live trading system.

## Constraints and facts

- Phase 1 persists `assets`, `ohlcv`, `events`, `metadata`, `runs`, and `lineage`.
- Analysis code reads local persisted data and never calls market or on-chain APIs.
- Canonical IDs remain unchanged; OHLCV idempotency is source-scoped so distinct
  provider observations are preserved.
- Results need dataset/version/config provenance; a result without those fields is
  not reproducible.
- New persistent tables or fields require the storage migration procedure and a
  schema-version bump.

## Proposed architecture

```text
storage readers -> point-in-time data views -> strategy API
                         |                     |
                         v                     v
                  eligibility/calendar    signals -> portfolio simulator
                                                       |
                                                       v
                                      fills, equity, metrics, run manifest
```

The first implementation should be a deterministic, bar-driven simulator with
explicit signal, portfolio, execution, and metric boundaries:

- `analysis/datasets/` builds read-only snapshots from DuckDB/Parquet and applies
  timestamp, source, lineage, and asset-eligibility rules.
- `analysis/strategies/` contains a narrow strategy protocol whose input is a
  point-in-time frame and whose output is target positions or orders.
- `analysis/backtesting/` owns the clock, order lifecycle, cash/position ledger,
  fees, slippage, missing-data policy, and fill assumptions.
- `analysis/metrics/` computes metrics from the persisted ledger, not from signal
  internals.
- `analysis/runs/` writes a manifest and immutable result artifacts locally.

The first execution model should be “signal observed at bar close, executable at
the next available bar open,” with configurable fees, slippage, and rejected-order
behavior. No intrabar precision, leverage, shorting, live orders, or optimization
is implied until separately designed and tested.

## Design decisions

1. **Point-in-time reads are mandatory.** A feature or metadata value must have an
   observation timestamp no later than the decision timestamp. Unknown values stay
   unknown; forward-filling across a token launch or metadata update is forbidden
   unless the dataset policy explicitly permits it.
2. **Strategies return intentions, not fills.** The simulator is the sole owner of
   cash, holdings, order validation, fees, slippage, and execution timing.
3. **Dataset manifests are first-class.** Each run records database/parquet input
   identity, query/policy version, time range, source filters, strategy/config
   hashes, and code version where available.
4. **Research outputs are separate from ingestion tables.** Additive result tables
   or files may be introduced only through a reviewed storage migration; raw Phase
   1 rows are never rewritten to make a backtest convenient.

## Alternatives considered

### Vectorized-only notebooks

Fast for simple OHLCV experiments, but weak at event timing, order state, missing
data, and reproducibility. Rejected as the system boundary; notebooks may consume
the framework later.

### Full event-driven exchange emulator

More realistic but requires order-book, latency, market-microstructure, and venue
semantics that Phase 1 does not collect. Deferred until evidence requires it.

### Third-party backtesting engine as the core

Could reduce initial implementation, but risks hiding look-ahead rules and making
the local schema/provenance contract secondary. Keep the first simulator small and
repository-owned; reassess after a benchmark strategy and validation corpus exist.

## Acceptance criteria

1. Given the same snapshot, strategy configuration, and simulator configuration,
   two runs produce byte-equivalent normalized trades, equity, metrics, and
   manifest inputs.
2. Given a feature published after a decision bar, the strategy cannot access it;
   a test with deliberately future-dated metadata fails closed or marks the value
   unavailable.
3. Given a buy signal at bar `t`, the earliest fill is governed by the documented
   next-bar rule, and fees/slippage appear in both the fill ledger and metrics.
4. Given duplicate, missing, halted, or insufficient bars, the configured policy
   produces an explicit outcome and never silently invents prices.
5. A minimal strategy can run entirely against fixture DuckDB/Parquet data with no
   network calls, and its result links back to a complete dataset/config manifest.
6. An attempted result with ambiguous asset identity, unavailable timestamps, or
   unsupported execution assumptions is rejected with an actionable error.

## Implementation slices and handoff

1. Freeze dataset snapshot and provenance contracts; add red tests for temporal
   joins and deterministic ordering.
2. Add read-only dataset loaders over the existing storage boundary; verify CEX,
   DEX, event, metadata, and lineage fixtures.
3. Add the strategy protocol and one trivial reference strategy; test signal
   determinism and no network imports/calls.
4. Add the next-bar simulator and ledger; test cash conservation, position limits,
   fee/slippage arithmetic, and missing-bar policies.
5. Add metrics and manifest persistence; test replay equality and failed-run
   recording.
6. Run an independent look-ahead and accounting review before adding more strategy
   features.

Natural handoff: a reviewed architecture plus acceptance matrix. Implementation
must begin with a storage-schema review if results become persistent tables.

## Planned repository surface and verification

Expected new paths are `analysis/datasets/`, `analysis/strategies/`,
`analysis/backtesting/`, `analysis/metrics/`, `analysis/runs/`, and focused tests
under `tests/`. Existing `storage/` files are modified only if the reviewed result
manifest needs canonical persistence. The first implementation should preserve the
repository’s existing `python -m pytest` command; fixture tests must run with
network access disabled. The acceptance run should include a replay of the same
fixture twice and an inspection of the generated manifest and ledger.

## Open decisions before implementation

- Whether Phase 2 results live only in versioned Parquet manifests initially or in
  DuckDB tables as well.
- The minimum supported asset universe and whether cross-venue execution is in the
  first slice.
- Whether returns are quote-currency only in the first release.
- The exact metric set and annualization convention.

## Resolved first-slice decisions

- Results are immutable, versioned JSON artifacts under `analysis/runs/`; the
  Phase 1 DuckDB schema is extended only through the reviewed versioned storage
  migrations; no analysis-owned persistent table is introduced.
- The first execution universe is one CEX venue at a time, with canonical asset
  identity required. DEX observations remain readable as local dataset inputs but
  are not executable by the first simulator.
- Returns and accounting are quote-currency only. The initial metric set is
  total return, maximum drawdown, annualized volatility, and annualized Sharpe,
  using a 365-day convention over daily observations.
- The initial strategy is a deterministic buy-and-hold reference strategy; no
  leverage, shorting, intrabar modeling, optimization, or live/paper execution is
  supported.

## Phase boundary

This document does not authorize strategy production, paper/live trading,
optimization, or alpha discovery. Those require separate acceptance criteria.
