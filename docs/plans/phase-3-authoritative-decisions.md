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
- The first implementation is baseline-first and does not require complex model
  training. Discovery uses Benjamini-Hochberg FDR at q=0.05; confirmatory holdout
  testing uses Holm-Bonferroni at alpha=0.05. The chronological split is 60/20/20
  with a 7-day embargo and a sealed final holdout.

The implementation is local-only and file-based; it does not change the Phase 1
storage schema or add provider access to analysis.
