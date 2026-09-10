# Phase 1 Codex Sub-Agents

Drop this package at the repository root. Codex discovers project-scoped custom agents from `.codex/agents/*.toml`.

## Agent set

| Agent | Mode | Primary use |
|---|---|---|
| `provider_contract_researcher` | read-only | Verify current external API/library contracts before implementation |
| `provider_adapter_worker` | workspace-write | Implement one isolated provider adapter behind a stable shared contract |
| `storage_schema_guardian` | read-only | Audit DuckDB/Parquet/schema/accessor/version/idempotency invariants |
| `goal_contract_reviewer` | read-only | Independently prove the active goal before advancing |
| `solana_ingestion_specialist` | workspace-write | Own architecturally separate Solana Tier 2 implementation slices |

## Recommended Phase 1 routing

- Goal 0: host or built-in `worker`; finish with `goal_contract_reviewer`.
- Goal 1: host/worker implementation -> `storage_schema_guardian` -> `goal_contract_reviewer`.
- Goal 2: `provider_contract_researcher` for ccxt semantics -> host/worker implementation -> `goal_contract_reviewer`.
- Goal 3: freeze normalized provider contract first -> parallel `provider_adapter_worker` instances for Dexscreener, GeckoTerminal, and DefiLlama with non-overlapping file scopes -> host integrates -> `goal_contract_reviewer`.
- Goal 4: parent freezes enrichment interface, normalized result/error types, routing/config contract first -> parallel `provider_adapter_worker` instances for Etherscan V2, Routescan, and BSCTrace/MegaNode; delegate separate RPC/risk-screen work only when file ownership does not collide -> host integrates -> `storage_schema_guardian` -> `goal_contract_reviewer`.
- Goal 5: `provider_contract_researcher` -> `solana_ingestion_specialist` -> `storage_schema_guardian` when persistence contracts changed -> `goal_contract_reviewer`.
- Goal 6: use built-in `explorer` agents for parallel identity/data-quality analysis; centralize implementation -> `storage_schema_guardian` -> `goal_contract_reviewer`.
- Goal 7: centralize scheduler integration; use `goal_contract_reviewer` for bounded end-to-end acceptance. Do not turn a sub-agent into an indefinite scheduler monitor.
- Goal 8: built-in `explorer` can reconstruct the landed architecture; host writes docs -> `goal_contract_reviewer` verifies documentation against implementation and Phase 1 scope freeze.

## Safe fan-out rule

Parallelize only work with exclusive ownership boundaries. The parent agent owns shared interfaces, schemas, routing registries, global configuration, and final integration unless it explicitly delegates one of those files to exactly one child.

For adapter fan-out, tell Codex the provider, allowed files, shared contracts that are frozen, whether all agents must finish before integration, and the required return format.

## Example invocation

```text
For the active goal, use the custom sub-agents in .codex/agents.
First use provider_contract_researcher where current provider/library behavior must be verified.
Before any parallel implementation, freeze the shared interfaces, normalized models, config contract, and file ownership.
Spawn provider_adapter_worker instances only for mutually exclusive provider scopes and wait for all of them before integrating.
After integration, run storage_schema_guardian when persistence/schema invariants are affected, then always run goal_contract_reviewer.
Do not advance to the next goal unless goal_contract_reviewer returns READY with every mandatory criterion PASS or the goal explicitly permits an UNVERIFIED runtime item.
```

## Permission note

Custom agents inherit session settings that they do not override. Source-review agents in this package explicitly request `read-only`; implementation specialists request `workspace-write`. The active Codex permission mode can still affect spawned agents, so select the intended session permissions before delegation.
