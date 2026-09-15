# AGENTS.md

## Purpose and scope

Applies to `normalization/`.

This subtree reconciles cross-source identity and reports local data quality. It is not a provider-ingestion layer and does not own schema design.

## Architecture and invariants

Reconciliation MUST use canonical asset evidence, especially contract/address identity. NEVER add symbol-only identity fallback.

For address matching, preserve current chain semantics: Solana address case is preserved; non-Solana matching follows the repository's normalized address behavior.

Create lineage only when a contract/address resolves to exactly one candidate. Ambiguous or missing matches MUST remain unlinked rather than guessed.

Reconciliation writes MUST use the canonical storage boundary and retain run accounting/error sanitization.

Do not mutate provider data merely to force a match.

Data-quality reporting MUST remain observational. It may report nulls, duplicates, future/prelaunch timestamps, and lineage state; it must not silently repair canonical data unless an explicit task adds a reviewed repair contract.

## Change boundaries

MUST NOT add external network/provider calls.

MUST NOT create schema or storage-access alternatives.

MUST NOT introduce research labels, alpha scoring, backtest logic, report claims, or trading behavior.

If reconciliation requires a new persisted field/table/key, hand that portion to the storage migration workflow rather than adding ad hoc DDL here.

## Testing requirements

Run:

```bash
python -m pytest tests/test_normalization.py
```

Changes that alter canonical identity assumptions SHOULD also run the relevant storage and analysis snapshot tests, because identity errors have cross-phase blast radius.

## Completion criteria

A normalization change is complete only when unambiguous matches link deterministically, ambiguous matches remain unlinked, storage/run-accounting behavior is preserved, focused tests pass, and applicable broader gates pass.
