# Solana Tier 2 — Helius

Load this when the task touches Helius, Solana mint/pool discovery, DAS, or enhanced transaction/webhook ingestion. Snapshot: September 2026. Current official Helius/Solana/program documentation supersedes this snapshot when verified.

## Researched free-tier budget

The supplied research records:

- **1,000,000 credits/month**;
- **10 RPS** standard RPC;
- **2 RPS** DAS & Enhanced APIs;
- **1 sendTransaction/sec**;
- standard RPC calls: 1 credit;
- `getProgramAccounts` and DAS: 10 credits;
- Enhanced Transactions: 100 credits/call.

Treat request-rate and credit-budget controls as separate constraints. A client can satisfy RPS and still exhaust monthly credits. Keep both in configuration/telemetry rather than burying them in adapter constants.

The researched Developer upgrade is $49/month with higher credits/RPS; purchasing or changing a plan is outside this skill's autonomous authority.

## Discovery signals and completeness

### Token mint signal

Enhanced webhook transaction type `TOKEN_MINT` on the Token Metadata Program can detect common creation patterns, but the supplied research explicitly warns that it can miss tokens minted through custom programs. Therefore `TOKEN_MINT` is a **signal**, not a completeness guarantee.

### Raydium pool signal

Research identifies Helius enhanced transaction types such as `CREATE_POOL`, or direct program monitoring for the Raydium AMM and its pool-initialization log. Verify current Raydium program contracts before production deployment; do not reconstruct program layout from memory.

### pump.fun / PumpSwap

The supplied research identifies both the pump.fun program and the PumpSwap migration path introduced in 2025. Monitor the currently configured programs required by the product's discovery definition. Do not hardcode program IDs into listener code; keep them in repository configuration and verify against current official/on-chain authority before production use.

The exact September 2026 research IDs are retained here only as reference evidence:

- Token Metadata Program: `metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s`
- Raydium AMM: `675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8`
- pump.fun: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`
- PumpSwap: `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`

A code change must source these from config, not copy them from this paragraph into executable code.

## Metadata / enrichment

DAS `getAsset` with fungible-token data is the researched metadata path. Price information is cached and limited in coverage, so absence of immediate USD price is not evidence that a new token is invalid. The legacy `/v0/token-metadata` route is deprecated in the supplied research; do not introduce new dependencies on it.

## Public RPC fallback

Public Solana RPC is a development fallback with no production SLA. The research records per-IP/method throttles; use it for noncritical development reads only and do not interpret a successful local fallback test as proof that production Helius auth/webhook behavior works.

## Risk screening gap

The supplied research does **not** establish a Solana equivalent for the EVM honeypot/rug-screen providers. Do not extend honeypot.is/GoPlus to Solana by analogy. If Solana risk screening is required, treat provider selection as unresolved until current authoritative research is supplied or performed.

## External side-effect boundary

Creating, deleting, or mutating Helius webhooks/subscriptions changes remote resources. A read-only smoke call may proceed when credentials are available and repository policy allows it; remote webhook mutation requires explicit authorization and must not be performed merely to satisfy the skill's live-verification step.
