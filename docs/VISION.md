# Vision

## Mission

`ccxt-crypto-pipeline` exists to give a serious, solo crypto researcher an
honest local record of what actually happened in CEX and DEX/on-chain
markets — and a research environment where a claimed "edge" cannot survive
by accident. Most retail crypto tooling skips straight to signals,
backtests, or execution and treats the data layer as a formality. This
project inverts that: data correctness, identity integrity, and
point-in-time discipline are the product, and every research or execution
capability built on top is gated behind proving it hasn't cheated.

## Problem

Crypto research is unusually easy to fool yourself with: symbol collisions
across chains and exchanges, silent forward-fill across gaps, providers that
substitute stale or synthetic values without saying so, and backtests that
leak future information into a "past" decision. Each of these produces a
strategy that looks profitable in review and fails (or was never real) in
practice — and the failure is invisible until it's expensive. There is no
convenient off-the-shelf pipeline that treats canonical identity, evidence
provenance, and leakage prevention as non-negotiable, enforced constraints
rather than best-effort intentions.

## Target Users

A single technically sophisticated operator — someone with quant/derivatives
or on-chain analytics background — running the entire stack locally: their
own credentials, their own DuckDB file, their own research judgment. Not a
hosted service, not a multi-tenant product, not a tool for people who want
signals handed to them. If this pipeline ever gains other users, they look
like this same profile, not a general retail audience.

## Core Principles

- **Ingestion is the only door to the outside world.** Analysis and
  reporting read local, persisted data and must work fully offline;
  nothing downstream may reach back out to a live provider.
- **Canonical identity over convenient identity.** `exchange:symbol` and
  `chain:contract_address` are the only valid identity keys. Symbol text
  alone never joins two assets, no matter how tempting the shortcut.
- **Point-in-time or it doesn't count.** A decision may use only what was
  observable at or before its decision time. No future leakage, no
  cross-boundary forward-fill, no fabricated values to smooth over gaps.
- **Missing stays missing.** Unsupported or absent data is recorded as
  unavailable, not silently substituted, interpolated, or defaulted.
- **Fail closed on ambiguity.** Ambiguous matches, unresolved conversions,
  and insufficient evidence block the specific claim rather than getting
  waved through.
- **Reproducibility is a hard requirement, not a nice-to-have.** Every run,
  dataset, and result carries deterministic ordering, configuration
  identity, and upstream lineage sufficient to replay it exactly.
- **A passing test is not a profitability claim.** Research surviving
  fixtures and offline validation earns the label "research result" —
  nothing more — until it survives an explicit, separate robustness and
  falsification gate.
- **Slow, evidenced, one-slice-at-a-time delivery beats a working demo.**
  The roadmap advances exactly one smallest independently verifiable slice
  at a time, with tests landing alongside it.

## Product Direction

The near-term frontier (Phase 7) is proving that any research result which
survives initial validation also survives deliberate attempts to break it:
effect-size gates, cost/liquidity stress, cohort and chain stability checks,
and negative/permutation controls designed to surface leakage. Beyond that,
Phase 8 turns validated research into locally reviewable, evidence-bound
report packages — with claim-level provenance back to source data — without
weakening any of the guarantees above. Optional paper execution (Phase 9)
and live execution (Phase 10) sit explicitly beyond the current product
commitment: they are not roadmap inevitabilities, they are separate future
decisions that would each require their own threat model, risk controls,
and authorization before a single line of order-placing code is written.

## Non-Goals

- Not a trading bot, signal service, or execution platform — today or by
  default tomorrow.
- Not a hosted, multi-tenant, or collaborative product.
- Not a place for predictive-alpha claims, profitability claims, or
  external publication as a side effect of research work.
- Not a strategy-optimization or paid-data-fallback engine that quietly
  papers over missing or unsupported information.
- Not a second, informal database or schema path that bypasses the
  canonical storage/migration boundary.

## Success Criteria

The vision is being honored when:

- A new contributor (human or AI agent) can determine the pipeline's real
  execution frontier from `AGENTS.md` + `ROADMAP.md` + `docs/plans/` alone,
  without reconstructing intent from chat history or commit messages.
- Every persisted observation can be traced to a specific provider, time,
  and canonical identity — with no code path capable of silently
  fabricating or mislabeling one.
- A promoted research candidate has survived the full negative-control and
  robustness suite, and its associated report package still reads as
  "here is what the evidence supports," not "here is why you should trade
  this."
- Adding a new provider, chain, or research capability never requires
  loosening the point-in-time, identity, or fail-closed invariants to fit
  it in.

## Future Possibilities

If the product commitment ever changes, the natural extensions are: richer
deterministic reporting formats (HTML/PDF) with the same claim-provenance
guarantees, an optional model-assisted drafting layer constrained to an
already-validated claim ledger, and — only behind explicit, separately
authorized design work — paper and eventually live execution with
independent risk controls, kill switches, and audit logging. None of these
are commitments; they are documented as the directions this foundation was
deliberately built to support without having to be re-architected first.
