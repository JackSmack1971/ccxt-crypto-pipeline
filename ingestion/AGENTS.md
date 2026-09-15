# AGENTS.md

## Purpose and scope

Applies to `ingestion/` and its provider-specific subpackages: `cex/`, `dex/`, `evm/`, and `solana/`.

This is the repository's only external crypto-provider I/O layer. It acquires, validates, normalizes, and persists observations; it does not perform research, scoring, backtesting, reporting, or trading.

For provider work, use `.agents/skills/crypto-ingestion-source/` as a procedure after confirming its examples against current code/tests/config/schema.

## Sources of truth

For an ingestion change, inspect the relevant adapter, `config/*.yaml`, `.env.example`, `storage/db.py`, and focused tests before editing.

Current provider behavior and repository tests outrank historical Skill snapshots or plan examples.

## Architecture and invariants

Provider-specific quirks MUST remain inside the corresponding adapter. Do not leak exchange/RPC/explorer behavior into `analysis/`, `reporting/`, `normalization/`, or `storage/`.

All persisted observations MUST use canonical storage accessors; do not open an alternate database or write Parquet directly from adapters.

Validate upstream identity, timestamps, prices, block/signature ranges, and required fields before persistence. Missing/invalid data MUST NOT become plausible defaults.

Preserve canonical identity and source attribution. Do not collapse assets by symbol text.

Respect configured provider routing, authentication, pagination, request budgets, timeouts, rate limiting, `Retry-After`, and bounded retry behavior.

Authentication/entitlement failures MUST NOT be retried as transient failures. `UNSUPPORTED`, `UNAVAILABLE`, transient failure, and successful availability MUST remain distinguishable.

Do not silently replace a configured provider with a paid or semantically different fallback.

## Cursor, continuation, and chain-state safety

Cursor and continuation state is durable in storage.

Advances MUST remain monotonic and use the implemented expected-prior / compare-and-set semantics.

If a requested range or continuation cannot be proven complete, fail closed and preserve the last durable progress point.

EVM ingestion MUST preserve canonical and orphaned block evidence and validate parent continuity according to the current listener/storage contract. Reorg handling MUST NOT erase evidence to manufacture a clean history.

Solana continuation/page limits MUST fail closed when the prior signature/token cannot be reached.

## Credentials and configuration

Credentials/RPC URLs MUST be read through the configured environment-variable boundaries in `.env.example` and `config/`.

Do not hardcode or print credentials, authenticated URLs, program/factory addresses, provider base URLs, or request budgets that belong in configuration.

Missing EVM/Solana credentials may cause scheduler paths to skip work. A skip is not live-provider success.

## Change boundaries

MUST NOT change persistent schema as an incidental provider edit; use the storage migration workflow when persistence changes.

MUST NOT change scheduler cadence/orchestration as an incidental adapter edit.

MUST NOT add trading, alpha scoring, portfolio decisions, backtest semantics, article logic, external webhook mutation, subscription creation, paid-plan activation, or deployment behavior.

## Testing requirements

Use deterministic fixtures for unit/CI verification. CI MUST NOT require provider credentials or live network access.

Focused tests currently include:

```bash
python -m pytest tests/test_cex.py tests/test_evm.py tests/test_solana.py
```

For Tier 0 DEX changes, run the focused test file(s) that exercise the changed `ingestion/dex/tier0/` code as present in the current test tree, plus the full suite when required.

When correctness depends on a real endpoint/auth/schema contract, a minimal authorized read-only smoke check may establish live compatibility. If it cannot be run, report live behavior as unverified rather than weakening fixtures or claiming production readiness.

## Completion criteria

An ingestion change is complete only when:

- provider routing/capability semantics remain explicit;
- normalized inputs are validated before persistence;
- replay does not create unintended duplicate canonical observations;
- cursor/continuation state cannot regress or skip unproven work;
- handled failures remain sanitized and observable;
- focused fixture tests pass;
- required broader repository gates pass;
- any live-provider evidence is separately identified.
