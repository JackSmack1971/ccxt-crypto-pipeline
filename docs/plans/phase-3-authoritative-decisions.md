# Phase 3 authoritative decisions

**Status:** Accepted design authority

This companion decision record resolves the open decisions in
`phase-3-new-token-alpha-discovery.md`.

- A launch is a unique `chain + contract_or_mint_address`; `t0` is the earliest
  defensible tradability observation. `first_seen` remains an observation boundary.
- Cohort membership is separate from analysis eligibility. The primary liquidity
  gate is USD-equivalent liquidity of at least $10,000 at `t0`, with $5,000,
  $25,000, and $50,000 sensitivity runs. Coverage requires at least 80% of
  expected observations and no contiguous gap over 25% of the interval.
- Labels are USD log forward returns at 1h, 6h, 24h, and 7d, using the fixed
  tolerance windows. Unavailable outcomes are explicitly economic, data, or right
  censored; missing values are never forward-filled.
- Quote-to-USD normalization uses versioned `ConversionPolicy` rules. Native USD
  quotes and policy-listed stablecoins record explicit endpoint-time parity;
  every other quote requires one unambiguous conversion observation at or
  before each label endpoint. That evidence may be supplied explicitly by the
  caller or read from the local persisted `reference_series` store (schema
  version 12) via `DatasetSnapshot.reference_series_at(f"{quote}/USD", point)`,
  a reusable point-in-time series contract not limited to label-boundary USD
  conversion. Missing, stale, or ambiguous conversion evidence produces data
  censoring, and label provenance retains the raw quote plus each conversion's
  timestamp, rate, source, and policy version.
- The first implementation is baseline-first and does not require complex model
  training. Discovery uses Benjamini-Hochberg FDR at q=0.05; confirmatory holdout
  testing uses Holm-Bonferroni at alpha=0.05. The chronological split is 60/20/20
  with a 7-day embargo and a sealed final holdout.

The implementation is local-only and file-based; it adds no provider access to
analysis. Phase 1 schema version 5 now retains timestamped metadata, lineage,
and source-scoped OHLCV history so point-in-time readers can select evidence at
or before the decision time.

## Verification record

`tests/test_phase3.py::test_phase1_to_phase3_replay_uses_persisted_snapshot_and_is_deterministic`
loads a real Phase 1 DuckDB fixture through `DatasetSnapshot.from_duckdb`, runs
cohort extraction, point-in-time features, labels, baseline candidate scoring,
and research artifact writing with network access denied, then repeats the run
and compares persisted artifacts byte-for-byte. This proves the narrow
Phase 1-to-Phase 3 fixture boundary; it does not establish complete live-data
coverage or predictive alpha. The companion
`test_research_run_identity_changes_when_evidence_content_changes` check proves
that a changed evidence artifact receives a different content-addressed run ID.
