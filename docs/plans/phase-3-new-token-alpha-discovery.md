# Phase 3 design pass: new-token alpha discovery methodology

**Status:** Implemented baseline methodology; complex downstream modeling remains deferred
**Date:** 2026-09-09
**Depends on:** Phase 1 persistence and Phase 2 point-in-time backtesting

## Goal

Create a falsifiable research methodology for discovering and evaluating signals
around newly observed tokens and pools. The output is a ranked, explainable
research dataset and candidate signal definitions—not an investment recommendation
or an automated trading decision.

## Constraints and facts

- Phase 1 has address-based DEX/CEX lineage, event timestamps, OHLCV, metadata,
  risk flags, and structured run records.
- New-token observations are incomplete and provider-dependent; “first seen” is an
  observation boundary, not proof of on-chain genesis.
- Solana and EVM identities remain distinct; chain and contract/mint address are
  required for joins.
- The methodology must preserve survivorship, selection, and look-ahead controls.
- It must use only local persisted inputs. Provider calls belong in ingestion.

## Proposed research pipeline

```text
observations -> cohort definition -> point-in-time features -> labels
       -> leakage/quality gates -> baseline comparisons -> ranked candidates
       -> Phase 2 replay/evaluation -> research report + provenance
```

The first cohort should be defined by a reproducible event rule (for example,
`new_pool_detected` or Solana `token_mint_detected`) within a declared date range,
chain set, and observation-quality threshold. Each token receives a stable cohort
row containing event time, first-observed time, source evidence, and exclusion
reason when it is not eligible.

Feature families should be explicitly separated:

- launch context: venue, chain, pool age, initial liquidity/volume when actually
  persisted;
- market behavior: returns, volatility, volume and drawdown computed only from
  bars after the feature timestamp;
- structure and risk: holder concentration, verification, LP and risk flags with
  their own observation times;
- cross-source adoption: lineage to a CEX and subsequent CEX observations, used as
  a label or later outcome—not as a launch-time feature unless already known.

Labels must declare horizon, censoring, quote currency, and whether delisted or
  unavailable assets count as failures. Candidate ranking must include coverage,
  confidence intervals or uncertainty bounds, turnover/cost sensitivity, and the
  number of independent launches—not only headline return.

## Design decisions

1. **Cohort-first, not winner-first.** All eligible launches and exclusions are
   retained so later review can detect survivorship and selection bias.
2. **Temporal feature registry.** Every feature definition declares source columns,
   effective timestamp, lookback, missing-value policy, and whether it is allowed
   for a given label horizon.
3. **Baselines are compulsory.** Compare candidates against no-trade, market/chain,
   age/liquidity, and simple momentum baselines where data supports them.
4. **Discovery and evaluation are separated.** Candidate generation may explore
   many features; the held-out evaluation set is sealed before ranking rules are
   changed.
5. **Risk is descriptive and explicit.** Missing or unsupported provider capability
   is not converted to a safe score. Risk flags retain provenance and uncertainty.

## Alternatives considered

### Supervised model first

Flexible but invites leakage, unstable labels, and opaque selection before the data
contract is mature. Rejected for the first methodology pass.

### Hand-authored indicator catalog only

Easy to explain but may miss interactions and encourages untracked manual tuning.
Useful as a baseline family, not the entire discovery method.

### Ranking by raw realized return

Simple but conflates opportunity, liquidity, costs, and survivorship. Rejected as a
primary selection rule; raw returns remain one diagnostic.

## Acceptance criteria

1. Given the same Phase 1 snapshot and cohort config, the same token cohort,
   exclusions, feature values, labels, and candidate ranking are reproduced.
2. A feature whose source timestamp is after the launch decision time is excluded
   and the exclusion is auditable; lineage discovered later cannot leak into a
   launch-time feature.
3. Every cohort member has an inclusion/exclusion reason, event/source evidence,
   and enough provenance to reproduce its feature row.
4. Candidate results report sample size, coverage, missingness, horizon/censoring,
   baseline comparison, cost sensitivity, and uncertainty; a low-coverage result
   cannot be presented as validated alpha.
5. A deliberately permuted-label or future-column fixture does not produce a
   passing leakage gate.
6. At least one candidate can be handed to the Phase 2 simulator without changing
   its temporal semantics, and the handoff manifest identifies the exact dataset,
   feature policy, labels, and evaluation split.
7. EVM and Solana candidates remain address-scoped and do not collapse identities
   from symbol text alone.

## Implementation slices and handoff

1. Freeze cohort, feature, label, split, and provenance schemas; obtain storage
   migration review for any persisted additions.
2. Build cohort extraction from `events`, `assets`, `metadata`, and `lineage`; add
   fixture cases for duplicate observations, missing metadata, late discovery, and
   both EVM/Solana IDs.
3. Implement temporal joins and the feature registry; test boundary timestamps,
   empty windows, and unsupported values.
4. Implement label generation and sealed train/discovery/evaluation splits; test
   delistings, censoring, and future-data rejection.
5. Implement baseline and candidate scoring with uncertainty and cost sensitivity.
6. Export a Phase 2-compatible strategy specification and a human-readable
   research report; review for leakage and overfitting before broadening the
   feature set.

Natural handoff: a signed-off methodology specification and a small fixture corpus,
not a claim that any candidate is profitable or production-ready.

## Planned repository surface and verification

Expected new paths are `analysis/alpha/` (cohorts, features, labels, evaluation),
versioned methodology/config files under `config/` only after their contract is
settled, and focused tests under `tests/`. Any persisted cohort, feature, label, or
result records must go through `storage/schema.py`/`storage/db.py` and the storage
schema-review gate. Verification uses the existing `python -m pytest` command plus
offline fixture runs that compare manifests, execute leakage fixtures, and inspect
the complete exclusion and provenance output.

## Deferred research questions

- “First observed” remains an observation boundary rather than proof of on-chain
  genesis; better genesis evidence would require a separately approved Phase 1
  ingestion enhancement.
- Complex model training remains deferred until the baseline evidence contract
  has broader real-data coverage.

The first-release gates, label horizons, quote-currency policy, censoring rules,
and multiple-testing corrections are resolved in
`phase-3-authoritative-decisions.md`.

## Phase boundary

This plan does not authorize live signals, automated execution, paid data, or a
claim of predictive alpha. Any external provider enhancement remains a Phase 1
ingestion change and must preserve the local analysis boundary.
