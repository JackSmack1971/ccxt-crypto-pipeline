# AGENTS.md

## Purpose and scope

Applies to `scheduler/`.

The scheduler is a thin coordinator around existing one-pass ingestion and normalization functions. It owns orchestration, run recording, cadence, and failure isolation; it MUST NOT reimplement provider or persistence semantics.

## Architecture and invariants

Keep `Pipeline` orchestration thin. Provider retries, cursor logic, canonicalization, storage semantics, and reconciliation belong in their owning modules.

A cycle currently executes:

1. CEX refresh
2. Tier 0 poll
3. EVM listeners
4. Solana listener
5. normalization

Preserve durable run outcomes. A failed job MUST remain visible as failed; do not convert exceptions into silent success.

Preserve per-chain EVM failure isolation so one configured chain failure does not prevent remaining chains from being attempted.

Missing configured EVM RPC or Solana API credentials may intentionally produce no work. Do not report that as provider verification.

Continuous scheduling uses UTC. Preserve `max_instances=1` and `coalesce=True` for registered jobs unless an explicitly approved orchestration redesign replaces the single-process assumptions.

Tier 0 cadence is currently clamped to the implemented 15–30 minute range.

## Change boundaries

MUST NOT duplicate provider clients or network logic in `scheduler/`.

MUST NOT bypass `storage.db` run/observation logging.

MUST NOT add a distributed worker/queue topology as an incidental scheduler refactor; the repository currently assumes local single-process orchestration around one DuckDB writer boundary.

Schedule changes that materially increase provider traffic MUST be treated as provider/runtime policy changes, not cosmetic edits.

## Verification commands

Run:

```bash
python -m pytest tests/test_scheduler.py
```

For health/status changes, also exercise the corresponding status/report behavior with deterministic local database fixtures.

After scheduler changes, run applicable ingestion/normalization focused tests when orchestration contracts changed, then repository-wide gates.

## Completion criteria

A scheduler change is complete only when job order/cadence behavior is intentional, failures remain recorded and isolated as designed, no provider/storage logic was duplicated, focused tests pass, and applicable broader gates pass.
