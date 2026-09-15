# AGENTS.md

## Purpose and scope

This repository is a local-first Python crypto data pipeline and research system.

Root instructions apply repository-wide. Deeper `AGENTS.md` files add or narrow rules for their subtree and take precedence there when consistent with higher-priority user/system instructions.

Prefer current code, tests, schemas, manifests, and configuration over stale prose. Do not treat roadmap text as implemented behavior.

## Sources of truth

When repository artifacts disagree, use:

1. Active user/system instructions.
2. Applicable accepted implementation/phase specification.
3. Current code, tests, schemas, manifests, and configuration.
4. `docs/durable-invariants.md`, `docs/architectural-constraints.md`, `docs/verification-expectations.md`, and `docs/operator-rules.md`.
5. Older plans, examples, architecture prose, and roadmap text.

MUST surface unresolved conflicts. NEVER manufacture a rule to reconcile inconsistent evidence.

Skills under `.agents/skills/` are procedures, not stronger authorities than current repository contracts. Confirm their examples against live code/tests/config before applying them.

## Repository map

- `ingestion/`: external provider/network access and pre-storage normalization.
- `storage/`: DuckDB schema/accessors/migrations, cursors, Parquet publication/recovery.
- `normalization/`: cross-source identity reconciliation and local quality reporting.
- `scheduler/`: orchestration over one-pass ingestion/normalization functions.
- `analysis/`: offline read-only datasets, backtesting, research, artifacts, experiments.
- `reporting/`: evidence-bound claims/charts and review-package generation.
- `config/`: runtime provider/chain/exchange/Solana configuration.
- `tests/`: executable contracts.
- `.agents/skills/`: task-specific workflows and helper guards.

Scoped instructions exist in the six top-level code packages above.

## Environment and setup

The package declares Python `>=3.10`; CI verifies Python 3.12.

Dependencies MUST remain consistent with `pyproject.toml` and `uv.lock`.

```bash
uv sync --locked --extra test
```

Local test wrappers are `scripts/run-tests` and `scripts/run-tests.ps1`.

Credentials/RPC URLs MUST stay in documented environment variables or untracked local configuration. NEVER commit `.env`, authenticated URLs, API keys, wallet material, or secret-bearing generated output.

## Build and verification commands

Run focused checks for the touched scope, then applicable repository-wide gates.

```bash
python -m pytest
python -m pytest tests/test_storage.py::test_v1_store_migrates_in_place_and_preserves_rows
python -m compileall -q analysis ingestion normalization reporting scheduler storage tests
git diff --check
```

`./scripts/run-tests` is the repository wrapper for the test suite.

Do not invent linter, formatter, type-checker, coverage, SAST, dependency-scan, release, or deployment gates not configured in the repository.

Report checks as `PASS`, `FAIL`, `NOT RUN`, or `BLOCKED`. Fixture/offline success MUST NOT be described as live-provider verification.

## Architecture and invariants

Only `ingestion/` may perform provider/exchange/explorer/RPC/on-chain network I/O.

DuckDB is canonical persistence; Parquet is derived publication state. MUST NOT create a second datastore or treat Parquet as recovery authority.

Persistent schema changes MUST stay in `storage/schema.py` / `storage/db.py`, use the versioned migration path, and preserve existing data unless an explicitly approved migration says otherwise.

Canonical asset identity MUST remain address/venue scoped. NEVER reconcile unrelated assets by symbol text alone.

Research/reporting MUST preserve point-in-time semantics: evidence observed or effective after decision time cannot influence that decision.

Missing, unsupported, ambiguous, or unavailable evidence MUST remain explicit. NEVER fabricate values or silently map uncertainty to safe/available state.

Content-addressed or immutable research/report artifacts MUST fail on conflicting overwrite.

Tests do not authorize live/paper trading, wallet custody/signing, external publication, or claims of profitability/predictive alpha.

## Security and external systems

NEVER log, persist, commit, or package secrets or secret-bearing URLs. Preserve current redaction and package security checks.

Security testing MUST be authorized and proportionate. Do not bypass third-party auth, paid tiers, rate limits, or protections; do not sign transactions or access wallets.

If a credential may be exposed, stop using it, retain sanitized evidence, and follow the repository security process.

## Change boundaries

MUST NOT weaken migration safety, validation, temporal/leakage gates, replay determinism, claim provenance, accessibility, secret scanning, or network-denial checks to make a change pass.

MUST NOT pull speculative roadmap work into the active task unless requested.

Use existing abstractions when their semantics fit. Do not add parallel logging, storage, provider routing, or artifact systems to avoid current contracts.

## Git and pull requests

Before editing or staging:

```bash
git status
git diff
git diff --cached
```

Preserve unrelated staged, unstaged, and untracked work. Stage only intended paths.

NEVER use `git reset --hard`, `git clean -fd`, checkout-discard, routine force-push, or history rewrite unless the user explicitly authorizes the exact recovery action.

Do not invent authors, reviewers, approvals, issues, or co-author trailers.

Remote operations, branch/PR actions, merging, pushing, signing, or deployment are conditional on the active task.

## Completion criteria

A task is complete only when the requested coherent scope is implemented, applicable scoped instructions were followed, relevant focused and repository-wide checks pass, the final diff was inspected, unrelated work/runtime data were preserved, verification is reported truthfully, and unresolved conflicts or unavailable required checks are explicit.
