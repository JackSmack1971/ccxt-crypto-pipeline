# Agent Instruction Architecture

This file documents where persistent coding-agent context belongs. It is a maintenance map, not an additional policy layer.

## Locality model

Keep the root `AGENTS.md` small and repository-wide. Place rules that only matter to one package in that package's `AGENTS.md`.

Current scopes:

| Scope | Owns |
| --- | --- |
| `AGENTS.md` | repository orientation, universal invariants, verification, security, Git safety |
| `ingestion/AGENTS.md` | external providers, routing, rate limits/retries, credentials, cursors, chain observations |
| `storage/AGENTS.md` | DuckDB/Parquet authority, schema migrations, persistence accessors, recovery |
| `normalization/AGENTS.md` | cross-source identity reconciliation and local quality reporting |
| `scheduler/AGENTS.md` | orchestration, cadence, failure isolation, run recording |
| `analysis/AGENTS.md` | offline datasets, backtests, research governance, experiments |
| `reporting/AGENTS.md` | approved handoffs, evidence-bound claims/charts, deterministic review packages |

Do not duplicate root rules in nested files unless a local exception or additional operational requirement is necessary.

## Durable reference material

Keep detailed evidence, enforcement inventories, gaps, and long-form explanations in:

- `docs/durable-invariants.md`
- `docs/architectural-constraints.md`
- `docs/verification-expectations.md`
- `docs/operator-rules.md`
- `docs/RUNBOOK.md`
- accepted phase/specification documents under `docs/plans/`

These files explain and evidence contracts. `AGENTS.md` files should extract only the instructions an agent must carry while editing the corresponding scope.

## Executable Skills

Use task-specific workflows rather than copying their procedures into `AGENTS.md`:

- `.agents/skills/one-slice-implementation/`
- `.agents/skills/crypto-ingestion-source/`
- `.agents/skills/storage-schema-migration/`
- `.agents/skills/evidence-bound-reporting/`

Skills are procedures and helper tooling. They MUST be checked against current repository code/tests/config before use; a Skill snapshot does not override a newer executable contract.

## Rule placement test

Before adding a rule, ask:

1. Does every repository change need this? Put it in root only if yes.
2. Does only one top-level package need it? Put it in that package's `AGENTS.md`.
3. Is it explanatory evidence, a runbook, a matrix, or historical context? Put it in `docs/`.
4. Is it a repeatable multi-step workflow with helper commands? Put it in `.agents/skills/`.
5. Is it already enforced completely by formatter/linter/tool configuration and adds no agent-specific constraint? Do not duplicate it.

Use `MUST`/`NEVER` only for evidence-backed hard constraints. Use `SHOULD` for strong defaults. If repository evidence is unresolved, document the uncertainty rather than creating a rule.
