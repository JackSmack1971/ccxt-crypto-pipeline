---
name: crypto-ingestion-source
description: Use when implementing, modifying, or debugging this pipeline's external crypto-data ingestion boundary: CCXT CEX adapters; DexScreener/GeckoTerminal/DefiLlama; EVM explorer or risk-screen clients; or Helius/Solana ingestion. Activates for provider/endpoint selection, auth/paywalls/rate limits, response normalization, canonical IDs, idempotent writes, and ingestion-run verification. Do not use for storage-schema migrations, scheduler/orchestration wiring, downstream analysis/scoring/trading, backtests, or generic API research that does not change ingestion behavior.
---

# Crypto Ingestion Source

This skill exists to implement or repair external-source ingestion when the task changes how crypto market or on-chain data is acquired, normalized, or verified before canonical storage.

## Authority and loading

1. **Local contract first.** Inspect repository schemas/models, `config/`, ingestion interfaces, tests, and run logging before editing. Do not invent tables, fields, config keys, or helper names from this skill.
2. **External contract second.** Current official provider docs and the repository's pinned client version govern endpoint/auth/schema behavior. Package references are a September 2026 research snapshot; they are not timeless truth.
3. **Conflicts stay visible.** If official docs, pinned-client behavior, repository code, and a reference disagree, do not guess. Treat the affected behavior as unverified until resolved. Update references only when task scope allows and authoritative evidence supports the change.
4. Load only the relevant branch:
   - Tier 0 aggregators → `references/tier0-aggregators.md`
   - EVM explorers/risk → `references/evm-tier1.md`
   - Solana/Helius → `references/solana-tier2.md`
   - CEX/CCXT → pinned CCXT + official CCXT/exchange docs; this research does not define CCXT endpoint semantics.
5. For researched providers, use `python scripts/provider_policy.py check ...` when practical. A nonzero result means the route is forbidden, unsupported by the snapshot, or requires current verification; do not override it from memory.

## Mandatory

- Preserve canonical identity: current design uses `exchange:symbol` for CEX and `chain:contract_address` for DEX/on-chain. Use `scripts/validate_canonical_id.py`; do not replicate parsing rules in adapters.
- Preserve idempotency. Current uniqueness contract: OHLCV `(canonical_id, timestamp, timeframe)`; events `(canonical_id, event_type, timestamp)`. Replaying the same normalized observation must not create a duplicate.
- Every attempted run must reach repository run accounting on success and handled failure. If its API differs from `log_run_start`/`log_run_end`, use the repository implementation rather than creating a parallel logger.
- Keep base URLs, credentials, chain/network lists, program/factory addresses, and request budgets in configuration, not adapter code. Never commit or print credentials, webhook secrets, or authenticated URLs.
- Enforce request budgets by provider **and endpoint class** where limits differ. Respect `Retry-After`; all retries must be bounded.
- Validate upstream data before persistence. Missing/invalid identity, timestamp, price, or event fields must not be converted into plausible values.
- Keep ingestion observational: acquire, validate, normalize, persist. No trading, alpha scoring, portfolio, backtest, or article decisions.
- Do not incidentally change schemas, production schedules, paid plans, credentials, remote webhook/subscription resources, deployments, or infrastructure. Use the owning workflow; externally consequential changes require explicit authorization.

## Provider decision rules

Route by **capability**, not one provider per chain. Load the relevant reference for exact limits/endpoints and use `provider_policy.py` to reject known-bad routes.

- Tier 0: GeckoTerminal → true new-pool discovery + DEX OHLCV; DexScreener → supplementary profiles/boosts + pair snapshots; DefiLlama → asynchronous TVL/yield context.
- EVM: Etherscan V2 is unified, but free entitlement varies by chain/capability. Base/BSC holder/deployer access must not be assumed free; verified-contract lookup is a separate capability.
- Solana: Helius is the researched native path. `TOKEN_MINT` is a signal, not proof of complete mint discovery; program IDs stay configurable.
- Risk: honeypot.is is researched only for Ethereum/BSC/Base and has no published numeric limit; GoPlus is the researched broader-EVM fallback. Screening evidence must not become a trading decision inside ingestion.

## Judgment

- Choose polling cadence, cache TTL, batch size, and bounded backoff from configured quota, freshness need, expected volume, and staleness cost. Jittered exponential backoff is a default, not an invariant.
- For overlapping providers, choose a primary by capability fit/quota/cost and use others for enrichment or discrepancy evidence. Never silently average conflicts or relabel a promotional feed as a strict new-pool feed.
- Choose the narrowest verification capable of disproving the likely failure. Mapping-only changes may be proven with fixtures/contracts; endpoint/auth changes need live compatibility evidence before production-ready claims.
- When evidence cannot distinguish upstream drift from local normalization error, report inconclusive rather than guessing a mapping.

## Evidence and completion

Establish a relevant baseline before behavior changes when the existing adapter/test can be exercised safely. Then verify every applicable layer:

1. repository-required static checks pass for touched code;
2. representative responses normalize correctly and malformed/partial inputs fail explicitly;
3. canonical IDs pass the helper and replay creates no duplicate observation;
4. success and handled-failure paths both produce expected run accounting without secret leakage;
5. researched provider/chain/capability routes pass `provider_policy.py`, or newer authoritative evidence is recorded;
6. when network + credentials are available, the smallest safe **read-only** smoke call proves live endpoint/auth/schema compatibility.

A change may be **locally verified** when 1–5 pass. It is **production-runtime verified** only when 6 is demonstrated wherever correctness depends on live provider behavior. If 6 cannot be run safely, report `UNVERIFIED_RUNTIME`; do not claim production readiness or create external state just to satisfy verification.

Separate pre-existing failures from introduced failures. Stop when applicable evidence is sufficient; unrelated expensive suites are not required merely to accumulate proof.

## Failure branches

| Divergence | Required response |
|---|---|
| Network/tool unavailable | Use deterministic fixtures/contracts for local proof; mark live evidence `UNVERIFIED_RUNTIME`. |
| Credential missing | Do not hardcode/print/bypass it; finish local proof where possible and report missing credentialed smoke evidence. |
| 429 / quota | Honor `Retry-After` or configured bounded backoff/jitter; record partial/retried outcome; do not increase pressure. |
| 401/403 / entitlement / paywall | Do not retry as transient. Check capability routing; use an alternative only when its required endpoint is verified. |
| 5xx / timeout | Retry only within bounded policy; after exhaustion record partial/inconclusive freshness. |
| Upstream schema drift | Capture minimal safe evidence; stop guessing; change mapping only from authoritative evidence. |
| Provider conflict | Preserve attribution, surface discrepancy, apply task-defined source priority; never silently merge incompatible facts. |
| Invalid canonical identity | Reject/skip and log data-quality failure; never invent a repaired address/symbol. |
| Pre-existing failing tests | Record baseline and use differential evidence; do not attribute old failures to the change. |
| Alternative provider details unresolved | Stop before claiming production readiness. |
| Paid-plan, credential rotation, production webhook mutation, deployment, or schedule change implied | Stop at implementation/config boundary and obtain explicit authorization or hand off. |

## Helpers

- `scripts/validate_canonical_id.py` — syntax/family validation; supported-chain membership deliberately remains repository configuration.
- `scripts/provider_policy.py` — checks the researched capability/paywall snapshot in `references/provider-capabilities.json`.
- `scripts/self_test.py` — offline regression test for helpers/registry. Run after editing this package.
