# EVM Tier 1 — Explorer and Risk-Screen Routing

Load this when the task touches Etherscan-family explorer data, Routescan/BSC alternatives, or EVM token risk screening. Snapshot: September 2026. Current official provider docs supersede this snapshot when verified.

## Etherscan V2 migration invariant

Legacy per-chain Etherscan-family APIs are obsolete for new work. Use the unified V2 base `https://api.etherscan.io/v2/api` with one Etherscan credential and `chainid=N`. V1 was deprecated in August 2025.

If repository config still contains names such as `BASESCAN_API_KEY`, `ARBISCAN_API_KEY`, or `BSCSCAN_API_KEY`, do **not** assume the variable name proves a valid modern credential contract. Inspect how it is consumed and migrate deliberately; do not silently rename secrets or change deployment configuration outside task scope.

## Capability and free-entitlement routing

The critical design rule is **per-capability provider routing**. A single `provider` field for an entire chain may be insufficient because verified-contract lookup and holder/deployer/transaction access can have different entitlements.

| Chain | Contract source / verification | Holders / deployer / general explorer data on researched free path |
|---|---|---|
| Ethereum | Etherscan V2 | Etherscan V2 |
| Arbitrum | Etherscan V2 (`chainid=42161`) | Etherscan V2 |
| Base | Etherscan V2 | Etherscan general free access is not available; Routescan is a researched alternative candidate but current auth details must be verified |
| BSC / BNB Chain | Etherscan V2 | Etherscan general free access is not available; BSCTrace/MegaNode is a researched migration direction, but exact endpoint/limit details are unresolved |
| Optimism | Etherscan V2 | Etherscan general free access is not available; Routescan is a researched alternative candidate |
| Avalanche C-Chain | Etherscan V2 | Etherscan general free access is not available; Routescan is a researched alternative candidate |

The supplied research states that Base, Optimism, BNB Chain, and Avalanche C-Chain lost general free Etherscan API access in November 2025, while verified-contract source/ABI access remains separately free. Do not generalize this table to unlisted chains without current verification.

Use `scripts/provider_policy.py check --provider etherscan_v2 --capability ... --chain ... --free-only` before claiming a researched free route.

## Rate-limit uncertainty

The research records a live Etherscan discrepancy: the rate-limit documentation says **5 calls/s**, while current pricing material says **3 calls/s** for the free selected-chain plan. Do not encode either as an unconditional truth. Configure the budget from the actual account entitlement/current official documentation; historical/name-tag endpoints also have separate caps.

Routescan is researched at **5 calls/s or 100,000/day**, but the supplied research does not conclusively establish current free-tier authentication details. `provider_policy.py` therefore blocks it as production-verified until current official docs are checked.

BSCTrace/MegaNode endpoint and limit details remain unresolved. Do not fabricate them.

## EVM risk screening

### honeypot.is

- Keyless in the supplied research.
- Researched chains: Ethereum (1), BSC (56), Base (8453).
- Endpoint: `/v2/IsHoneypot?address={token}` with optional chain/pair parameters.
- **No provider-published numeric rate limit is established.** Conservative self-throttling/caching is skill policy, not an official quota.

### GoPlus

The supplied research identifies GoPlus as the broader-chain EVM fallback. Official documentation in the research says 30 calls/minute, but a newer compute-unit model may be emerging. Verify current limits before sizing production polling.

Decision: Ethereum/BSC/Base may use honeypot.is first; other supported EVM chains use a verified GoPlus route. Record which provider produced the risk evidence when the repository schema supports provenance. Never turn a risk-screen response into a trading action inside ingestion.

## Addresses and configuration

DEX factory/program addresses are DEX- and chain-specific and are **not established by this research**. Obtain them from the DEX's current official documentation and keep them in repository configuration, never embedded in listener code.

## Stop conditions

Stop before claiming production readiness when:

- an alternative explorer's endpoint/auth details are unresolved;
- current account entitlement is unknown and the route depends on free-vs-paid access;
- a legacy explorer credential cannot be proven to work with the unified V2 contract;
- a provider response schema conflicts with both repository expectations and current official docs.
