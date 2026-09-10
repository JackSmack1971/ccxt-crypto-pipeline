# AGENTS.md

## Purpose and scope

This repository implements **Phase 1 only** of a crypto research system: a local data-ingestion pipeline that collects CEX and DEX/on-chain data, normalizes it, and persists it for later use.

The architecture MUST preserve these boundaries:

- Ingestion and analysis are strictly decoupled. Ingestion jobs fetch external data on a schedule and write to local storage.
- Future analysis, backtesting, alpha-scoring, and article-generation layers MUST read persisted data and MUST NEVER call live market/on-chain APIs directly.
- CEX ingestion uses `ccxt` public/free endpoints.
- DEX/on-chain ingestion is tiered:
  - Tier 0: Dexscreener, GeckoTerminal, and DefiLlama across configured chains.
  - Tier 1: shared EVM ingestion for Ethereum, Base, Arbitrum, and BSC, with direct RPC observation separated from provider-specific enrichment.
  - Tier 2: Solana, architecturally separate from EVM, using Helius or an explicitly chosen equivalent.
  - Tier 3: all other chains remain aggregator-only in Phase 1.
- Persistent storage is local DuckDB + Parquet. Hosted databases and paid infrastructure are out of scope.
- Analysis, backtesting, strategy logic, alpha scoring, article generation, and visualization-generation features MUST NOT be added during Phase 1.

## Instruction scope

This file is root repository guidance.

- A nested `AGENTS.md` SHOULD exist only when a subtree needs genuine exceptions or additional constraints; it MUST NOT duplicate this file.
- An `AGENTS.override.md` in a directory replaces `AGENTS.md` guidance for that same directory in Codex.
- More specific active user instructions and the active goal specification take precedence over broader repository guidance.

## Sources of truth

Use these sources in this order:

1. The active user-provided goal prompt defines the current checkpoint and its allowed scope.
2. `codex-goals-phase1-data-pipeline-updated.md`, when present in the repository, defines the Phase 1 goal order, deliverables, architecture context, and acceptance criteria.
3. Existing code, tests, configuration, and documentation from already completed goals define the implemented contract that later goals MUST preserve.

If the phase specification is not checked into the repository, do not reconstruct missing details from memory. Use the active goal prompt and established repository artifacts.

External provider behavior is mutable. When a goal requires a live provider, the implementation MUST be checked against current official provider documentation for endpoints, authentication, capabilities, and published rate limits. Keep mutable provider details in adapters/configuration rather than duplicating them here.

## Sequential goal execution

Phase 1 consists of Goals 0 through 8 and MUST be executed one checkpoint at a time, in order.

- Work only on the active goal.
- NEVER implement deliverables that belong to a later goal, even when they appear convenient or are obvious next steps.
- Preserve all acceptance criteria and architectural contracts established by completed goals.
- If the active goal exposes a defect in an earlier goal, make only the minimum backward-compatible correction needed for the current goal and report it.
- Do not advance to the next goal until the current goal has been reviewed or the user explicitly requests advancement.
- Do not claim an acceptance criterion passed unless it was actually verified.
- If a live acceptance criterion cannot be exercised because credentials, network access, provider availability, or another external prerequisite is missing, report that criterion as blocked with the concrete reason. NEVER fabricate a successful integration result.
- Goal 0 requires an initial git commit. Do not assume later goals require commits unless explicitly requested.

Before editing, inspect the repository for completed-goal artifacts, current configuration, tests, and existing conventions. Do not overwrite working prior-goal behavior merely to match a preferred implementation style.

## Sub-agent orchestration

Project-scoped custom agents are defined in `.codex/agents/*.toml`. Multi-agent execution is a controlled optimization for context isolation, independent evidence, and safe parallelism; it is not a reason to fragment tightly coupled work.

### Parent/orchestrator responsibilities

The primary agent owns the active goal end to end. It MUST:

- reconstruct the active goal before delegation and preserve its MUST/MUST NOT requirements, acceptance criteria, and scope boundaries;
- decide whether delegation is actually useful; do not spawn a sub-agent for trivial repository inspection, a single small edit, or work whose state must be continuously shared with the parent;
- own decomposition, shared-contract design, cross-agent integration, conflict resolution, and the final checkpoint decision;
- keep shared schemas, normalized interfaces, cross-provider result/error models, routing registries, and global configuration parent-owned unless exactly one child is explicitly assigned exclusive ownership;
- wait for all parallel children in a fan-out before integrating their results;
- treat child reports as evidence inputs, not proof of completion;
- prevent every child from implementing later-goal work or weakening an established earlier-goal contract;
- avoid recursive delegation by children unless the active task explicitly assigns orchestration authority to that child.

Use the built-in `explorer` for read-heavy repository mapping and evidence gathering when a custom specialist is unnecessary. Use the built-in `worker` for cohesive implementation work that does not require one of the specialized roles below.

### Custom-agent routing

Use these project agents according to responsibility, not merely because they exist:

- `provider_contract_researcher` — read-only. Use before implementing or materially changing behavior that depends on a mutable external provider/library contract: ccxt, Dexscreener, GeckoTerminal, DefiLlama, Etherscan, Routescan, BSCTrace/MegaNode, Helius, RPC/provider semantics, or risk-screen APIs. It establishes current endpoints, authentication, pagination, rate limits, free-tier capabilities, response/error shapes, and unsupported states from authoritative sources. It does not implement.
- `provider_adapter_worker` — implementation specialist. Use only after the parent has frozen the normalized interface, result/error semantics, configuration contract, and file ownership for the delegated provider. Parallel instances are allowed only for mutually exclusive provider/file scopes. It MUST NOT redesign shared contracts, routing registries, canonical storage, or unrelated providers unless the parent explicitly delegates one of those artifacts to that single worker.
- `storage_schema_guardian` — read-only storage reviewer. Use after implementing Goal 1 and after any later work that changes or materially relies on DuckDB/Parquet DDL, `SCHEMA_VERSION`, initialization, canonical IDs, persistence keys/idempotency, partitioning, `storage/db.py`, or schema extensions such as `lineage`. It audits; it does not repair findings.
- `solana_ingestion_specialist` — implementation specialist for Goal 5 and other explicitly Solana-specific Tier 2 work. Keep Helius/Solana/Raydium/Orca/pump.fun semantics separate from EVM assumptions while preserving the shared `events`/`metadata` storage meaning and `solana:mint_address` identity contract.
- `goal_contract_reviewer` — read-only final acceptance reviewer. Use after implementation and integration for **every Goal 0–8**, before the parent declares the checkpoint complete or advances. It independently reconstructs the goal, traces actual evidence, detects scope creep and pulled-forward work, and reports PASS/FAIL/UNVERIFIED per criterion. It MUST NOT fix its own findings.

### Goal-specific delegation pattern

Default to the following topology unless repository evidence makes a simpler path sufficient:

| Goal | Preferred execution                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0    | Parent or built-in `worker` → `goal_contract_reviewer`                                                                                                                                                                                                                                                                                                                                                                |
| 1    | Parent/`worker` implements cohesive storage layer → `storage_schema_guardian` → `goal_contract_reviewer`                                                                                                                                                                                                                                                                                                              |
| 2    | `provider_contract_researcher` verifies ccxt semantics → parent/`worker` implements CEX subsystem → `goal_contract_reviewer`                                                                                                                                                                                                                                                                                          |
| 3    | Research provider contracts as needed → parent freezes common Tier 0 contracts → parallel `provider_adapter_worker` instances for mutually exclusive Dexscreener / GeckoTerminal / DefiLlama scopes → parent integrates → `goal_contract_reviewer`                                                                                                                                                                    |
| 4    | Research provider/RPC contracts as needed → parent freezes enrichment interface, normalized types, provider routing/configuration, and ownership → parallel provider workers only for exclusive Etherscan / Routescan / BSCTrace-MegaNode scopes; separate RPC/risk work only when ownership does not collide → parent integrates → `storage_schema_guardian` when persistence is affected → `goal_contract_reviewer` |
| 5    | `provider_contract_researcher` verifies current Solana/provider/venue behavior → `solana_ingestion_specialist` → `storage_schema_guardian` if shared persistence changed → `goal_contract_reviewer`                                                                                                                                                                                                                   |
| 6    | Built-in `explorer` agents may independently analyze identity reconciliation and data-quality paths → parent centralizes implementation → `storage_schema_guardian` → `goal_contract_reviewer`                                                                                                                                                                                                                        |
| 7    | Parent/`worker` owns scheduler integration; do not split the coupled scheduler state across competing writers → bounded end-to-end verification → `goal_contract_reviewer`                                                                                                                                                                                                                                            |
| 8    | Built-in `explorer` may reconstruct the landed implementation → parent/`worker` updates documentation → `goal_contract_reviewer` verifies docs against the actual tree and Phase 1 freeze                                                                                                                                                                                                                             |

This table is a routing default, not permission to pull work forward. The active goal remains authoritative.

### Delegation contract

Every delegated task MUST give the child enough bounded context to work independently without rediscovering or redefining the project contract. Include, as applicable:

- `ACTIVE_GOAL`: the current checkpoint and relevant acceptance criteria;
- `OBJECTIVE`: one concrete delegated outcome;
- `ALLOWED_SCOPE`: directories/files/symbols the child may inspect or modify;
- `FROZEN_CONTRACTS`: interfaces, schemas, models, configuration, and semantics the child must preserve;
- `MUST_NOT`: active prohibitions, later-goal boundaries, paid-infrastructure restrictions, secret-handling constraints, and shared files it must not mutate;
- `EVIDENCE_REQUIRED`: tests, commands, source references, or runtime evidence expected back;
- `RETURN_FORMAT`: concise findings/changes, verification outcomes, blockers, and requested parent-owned changes.

For parallel write agents, `ALLOWED_SCOPE` MUST be mutually exclusive. If two children would need to edit the same shared file or make interdependent changes to the same abstraction, do not run those writes in parallel; centralize or serialize them.

Unless explicitly delegated by the active goal or parent, sub-agents MUST NOT commit, merge, rebase, push, rewrite Git history, change global Codex configuration, or modify unrelated repository control-plane files.

### Evidence and review gate

Sub-agent completion does not satisfy an acceptance criterion by itself.

- The parent integrates and verifies all child work against the authoritative repository state.
- Fixture/mock evidence MUST NOT be used to claim a live acceptance path passed.
- A required live check that cannot run because credentials, network, provider availability, or environment support is missing remains `UNVERIFIED`/blocked exactly as required by the active goal; do not manufacture substitutes.
- After material corrections prompted by `storage_schema_guardian` or `goal_contract_reviewer`, rerun the relevant reviewer rather than assuming the findings are resolved.
- The parent MUST NOT automatically advance with any mandatory criterion at `FAIL` or `UNVERIFIED`. A blocked external prerequisite requires an explicit user decision to proceed despite the unresolved criterion.

Child sandboxes and other session settings follow their agent configuration and inherited Codex permissions. Do not loosen repository permissions merely to make delegation convenient.

## Repository map

The Phase 1 design assigns these boundaries:

- `ingestion/cex/` — CEX universe discovery, OHLCV backfill, and refresh.
- `ingestion/dex/tier0/` — chain-agnostic aggregator clients and polling.
- `ingestion/evm/` — shared EVM RPC observation plus normalized enrichment interfaces and provider adapters.
- `ingestion/solana/` — Solana-specific Tier 2 ingestion; do not fold it into the EVM abstraction.
- `normalization/` — cross-source reconciliation and data-quality jobs.
- `storage/` — canonical schema, initialization, persistence, and read/write access. This is the persistence boundary for all ingestion.
- `scheduler/` — orchestration, scheduling, run status, and health reporting.
- `config/` — runtime configuration such as CEX settings, chain settings, provider routing, RPC endpoints, and non-secret defaults.
- `tests/` — fixture/unit/integration tests required by the active goal.
- `docs/` — Phase 1 architecture and runbook documentation.

Do not create parallel storage abstractions, per-chain EVM implementations, or analysis-layer directories that bypass these boundaries.

## Environment and configuration

Goal 0 establishes the Python project and must include pinned dependencies for at least:

`ccxt`, `duckdb`, `pyarrow`, `pandas`, `requests`, `python-dotenv`, `apscheduler`.

Use the repository's chosen dependency file (`pyproject.toml` or `requirements.txt`) consistently after bootstrap. Do not invent a second package-management path without a demonstrated need.

`.env.example` MUST contain placeholders only. Real secrets MUST NOT be committed.

The environment-variable contract includes:

- `ETHERSCAN_API_KEY` — shared Etherscan V2 credential for supported Etherscan-routed chains, including Ethereum and Arbitrum.
- `ROUTESCAN_API_KEY` — Base enrichment credential when configured; supported keyless Routescan access may be intentionally selected.
- `MEGANODE_API_KEY` — MegaNode/BSCTrace credential for BSC enrichment.
- `HELIUS_API_KEY` — Solana Tier 2 credential.
- `EVM_RPC_URL_ETHEREUM`
- `EVM_RPC_URL_BASE`
- `EVM_RPC_URL_ARBITRUM`
- `EVM_RPC_URL_BSC`

`BASESCAN_API_KEY`, `ARBISCAN_API_KEY`, and `BSCSCAN_API_KEY` are obsolete for this project and MUST NOT be introduced.

Direct RPC URLs and explorer/indexer credentials are independent configuration concerns and MUST remain separately configurable.

Local `.env` files, DuckDB database files, Parquet data directories, virtual environments, and Python build/cache artifacts MUST remain ignored by git.

## Build and verification commands

Only treat commands as authoritative when they are present in the active goal or established by repository configuration.

Phase-specified commands include:

- Inspect Goal 0's initial commit with `git log`.
- CEX backfill acceptance path:
  `python -m ingestion.cex.backfill --exchange kraken --symbol BTC/USDT --timeframe 1d --since 2023-01-01`
- Scheduler health check after Goal 7:
  `python -m scheduler.status`

The phase specification does not prescribe a universal test-runner command. Discover the configured test command from repository files before using or documenting one; do not invent it.

When reporting completion, state the exact commands run and their outcomes. For commands requiring live services, distinguish fixture/unit verification from real integration verification.

## Storage and schema invariants

`storage/` is the single canonical persistence layer for later ingestion and future analysis.

The canonical Phase 1 tables are:

- `assets`
- `ohlcv`
- `events`
- `metadata`
- `runs`
- `lineage` after Goal 6

Canonical IDs MUST use:

- CEX: `"exchange:symbol"`
- DEX/EVM: `"chain:contract_address"`
- Solana: `"solana:mint_address"`

Preserve these data rules:

- `assets.canonical_id` is the asset identity key.
- OHLCV persistence MUST be idempotent on `canonical_id + timestamp + timeframe`.
- OHLCV Parquet data MUST be partitioned by `source` and date.
- Every ingestion job MUST write run status to `runs`, including job name, timing, status, row count, and any error.
- `SCHEMA_VERSION` and idempotent schema initialization MUST exist once Goal 1 is implemented.
- `storage/db.py` is the thin shared data-access boundary. Ingestion modules SHOULD call its storage operations rather than embedding independent DuckDB write logic.
- New schema introduced by a later goal, such as `lineage`, MUST extend the canonical storage contract rather than create a separate database.

Do not silently change canonical-ID formats or table semantics after downstream goals depend on them.

## CEX ingestion invariants

Once Goal 2 is active or complete:

- Exchange list, timeframes, lookback window, and volume thresholds belong in `config/cex.yaml`, not hardcoded in ingestion modules.
- Universe discovery uses `ccxt` market/ticker data and filters to configured spot markets above the configured minimum 24-hour volume.
- Historical OHLCV backfill MUST use `since`-based pagination and MUST be resumable per exchange/symbol/timeframe.
- Incremental refresh MUST fetch only new candles since the persisted checkpoint and include the required ticker snapshot.
- Respect `ccxt`'s built-in rate limiter and add exponential backoff for transient failures.
- Re-running the same backfill MUST NOT create duplicate OHLCV rows.

## DEX Tier 0 invariants

Once Goal 3 is active or complete:

- Tier 0 uses Dexscreener, GeckoTerminal, and DefiLlama behind chain-agnostic ingestion logic.
- Networks are configuration-driven through `config/chains.yaml`.
- New-pool and trending detections write normalized `events` rows using `new_pool_detected` or `trending`.
- Newly observed tokens are registered in `assets` with `source_type="dex"`.
- API throttling MUST respect each provider's published limits and SHOULD be implemented through shared rate-limit/throttle utilities rather than scattered sleeps.

Tier 0 is the universal fallback. Chains without a Phase 1 deep adapter remain aggregator-only.

## EVM Tier 1 invariants

`ingestion/evm/` MUST use one shared EVM implementation for common RPC/event conventions across Ethereum, Base, Arbitrum, and BSC.

Two infrastructure concerns MUST stay separate:

1. Direct RPC access for block/log/event observation.
2. Explorer/indexer providers for historical/indexed enrichment.

The RPC listener is chain-parameterized and configuration-driven, including chain → RPC URL and known DEX factory addresses. Common `PairCreated`/`PoolCreated`-style observation belongs in shared logic.

The normalized enrichment interface MUST expose the equivalent of:

- `is_contract_verified(address)`
- `get_top_holders(address)`
- `get_deployer_address(address)`

Shared ingestion/enrichment code MUST consume that normalized interface. Chain-specific HTTP request construction, authentication, base URLs, chain IDs, retries/backoff, rate limits, parsing, and capability differences MUST remain inside provider adapters/configuration.

Required enrichment routing:

| Chain                 | Provider          | Credential / routing                                                                 |
| --------------------- | ----------------- | ------------------------------------------------------------------------------------ |
| Ethereum              | Etherscan V2      | `chainid=1`, `ETHERSCAN_API_KEY`                                                     |
| Arbitrum              | Etherscan V2      | `chainid=42161`, same `ETHERSCAN_API_KEY`                                            |
| Base                  | Routescan         | `ROUTESCAN_API_KEY` when configured; intentional supported keyless access is allowed |
| BSC / BNB Smart Chain | BSCTrace/MegaNode | `MEGANODE_API_KEY`                                                                   |

NEVER route Base or BSC to paid Etherscan endpoints as an automatic fallback.

If the configured free provider cannot supply a required capability, surface that capability explicitly as `UNSUPPORTED` or an equivalent explicit unavailable state. NEVER fabricate a value, silently omit the limitation, or substitute semantically different data.

A free honeypot/rug-screen integration may provide normalized risk information; its result belongs in `metadata.risk_flags_json`.

## Solana Tier 2 invariants

`ingestion/solana/` is architecturally separate from the EVM implementation.

Once Goal 5 is active or complete:

- Detect new token mints and new pool creation for the required Solana venues through Helius or the explicitly selected equivalent.
- Fetch holder distribution and token metadata for newly detected mints.
- Normalize into the same canonical `events` and `metadata` storage used by the EVM path.
- Use `canonical_id = "solana:mint_address"`.

Do not force Solana provider semantics through EVM RPC or explorer abstractions.

## Normalization and data-quality invariants

Once Goal 6 is active or complete:

- Reconcile DEX assets that later appear on CEXs using contract-address evidence where exchanges publish it.
- Record cross-source identity in `lineage(dex_canonical_id, cex_canonical_id, linked_at)`.
- Preserve both canonical IDs; lineage links them rather than replacing one identity with the other.
- Data-quality checks MUST cover nulls, duplicates, future timestamps, pre-launch timestamps, and daily row-count summaries by source/job.
- Do not infer a DEX↔CEX identity from symbol text alone when contract-address evidence is required by the goal.

## Scheduling invariants

Once Goal 7 is active or complete, orchestrate existing jobs without moving provider-specific logic into the scheduler.

Required cadence:

- CEX refresh: daily.
- Tier 0 DEX poll: every 15–30 minutes.
- Tier 1/2 listeners: continuous or tight-interval polling.
- Normalization: nightly.

Scheduler failures MUST be reflected in structured `runs` records and MUST NOT terminate the full scheduler through an unhandled exception when the failure can be isolated to a job.

`python -m scheduler.status` is the Phase 1 CLI health-check entry point.

## Testing requirements

Testing MUST follow the active goal's acceptance criteria.

- Goal 1: create a database from scratch, insert fixture data into every table, and read back matching values. No real external API calls.
- Goal 2: verify real OHLCV ingestion and prove a repeated backfill creates zero duplicate rows.
- Goal 3: manually verify real new-pool data on at least three different networks and normalized writes.
- Goal 4: fixture/unit tests MUST prove provider routing, common normalized shapes, shared Ethereum/Arbitrum credential behavior, RPC/credential independence, and explicit unsupported-capability handling with no paid fallback. The live acceptance path MUST enrich at least one recent EVM pair-creation event end-to-end using only free-tier/free-access infrastructure.
- Goal 5: manually verify at least one recent Solana launch produces structurally comparable metadata.
- Goal 6: verify one real token known on both DEX and CEX resolves to one lineage link.
- Goal 7: verify one complete local scheduler cycle populates CEX, Tier 0, and at least one Tier 1 chain with a clean status report and no unhandled exceptions.

Unit tests SHOULD use fixtures/mocks for external services unless the acceptance criterion explicitly requires a live integration. A mocked test MUST NOT be reported as satisfying a live acceptance criterion.

Tests for provider normalization SHOULD cover malformed, empty, rate-limited, unsupported, and transient-error responses when those cases are relevant to the implemented adapter.

## Security and external systems

- Use free public/free-tier infrastructure only for Phase 1.
- NEVER commit credentials or real secret values.
- NEVER log API keys, RPC credentials, or complete secret-bearing request URLs.
- Respect provider-published rate limits and transient-error behavior.
- Keep credentials in environment configuration and non-secret routing/capability metadata in project configuration.
- Do not add hosted databases, paid fallbacks, or paid-only dependencies to make an acceptance test pass.
- When provider capabilities differ, preserve the semantic distinction instead of manufacturing uniformity.

## Documentation requirements

Documentation MUST describe implemented behavior, not aspirational future architecture.

At Goal 8:

- `docs/ARCHITECTURE.md` MUST document final Phase 1 structure, schema, data flow, EVM RPC vs. explorer/indexer separation, and chain → enrichment-provider routing.
- `docs/RUNBOOK.md` MUST document local execution, monitoring, debugging, the final environment-variable contract, and provider-specific credential setup.
- `README.md` MUST describe the completed Phase 1 ingestion pipeline.

Massive runbooks, API details, or provider reference material SHOULD live in dedicated docs and be referenced from here rather than copied into `AGENTS.md`.

## Completion criteria

A goal is complete only when:

- Its required deliverables exist and stay within the active goal's scope.
- Relevant tests/verification pass, or any blocked live criterion is reported precisely.
- Previously completed goal contracts still hold.
- No later-goal implementation was pulled forward.
- No secret, paid-infrastructure dependency, obsolete credential variable, or architectural bypass was introduced.
- The completion report identifies changed files, verification commands and results, external/live checks performed, and unresolved blockers.
- Goal 0 additionally reports the final tree and verifies the initial commit.
- Goal 8 explicitly confirms that no analysis, backtesting, alpha-scoring, or article-generation code exists and freezes Phase 1 at that boundary.
