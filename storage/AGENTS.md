# AGENTS.md

## Purpose and scope

Applies to `storage/`.

`storage/schema.py` and `storage/db.py` own the repository's canonical persisted contract. DuckDB is authoritative; Parquet is derived publication state.

Use `.agents/skills/storage-schema-migration/` for persisted schema/partition/vocabulary changes.

## Sources of truth

Current `storage/schema.py`, `storage/db.py`, and `tests/test_storage.py` are the executable storage contract.

`SCHEMA_VERSION` is defined in `storage/schema.py`; do not copy a version number from older architecture prose.

## Architecture and invariants

MUST keep table/column/constraint definitions and migration logic in the canonical storage boundary.

MUST NOT create an alternate DuckDB, SQLite/Postgres path, direct Parquet authority, or ad hoc schema-defining module to bypass storage review.

DuckDB commit state remains authoritative even if Parquet publication fails. Recovery MUST rebuild derived Parquet from DuckDB rather than re-ingesting committed observations.

All error text written durably MUST continue through the repository's redaction/safe-error boundary.

Cursor and continuation accessors MUST preserve monotonic / compare-and-set semantics.

EVM block observation storage MUST preserve canonicality history rather than deleting orphan evidence.

## Schema migrations

Any change to persisted tables, columns, keys, constraints, partitioning, or persisted vocabulary MUST:

1. update the canonical schema/accessors;
2. advance `SCHEMA_VERSION`;
3. provide a sequential migration from prior supported state;
4. be transactional/recoverable where the current mechanism supports it;
5. be idempotent on repeated initialization;
6. preserve existing representative rows unless explicitly authorized otherwise;
7. keep fresh initialization and migrated initialization convergent;
8. add or update storage migration tests.

Opening a database whose schema version is newer than the running code MUST continue to fail closed.

Do not rely on `CREATE TABLE IF NOT EXISTS` as a migration for an existing changed table.

## Parquet publication and recovery

Verify derived publication with:

```bash
python -m storage <db> --verify-parquet
```

Repair divergence from DuckDB with:

```bash
python -m storage <db> --repair-parquet
```

Use the repository's `--parquet-dir` option for a nondefault layout.

MUST NOT treat Parquet as canonical input to overwrite DuckDB.

## Writer safety

Do not delete DuckDB/Parquet state while a writer is running.

Do not intentionally run competing writer/scheduler processes against the same database file. In-process APScheduler overlap controls are not a multiprocess coordination mechanism.

## Testing requirements

Storage changes MUST run focused storage tests.

Schema changes MUST run:

```bash
python -m pytest tests/test_storage.py::test_v1_store_migrates_in_place_and_preserves_rows
python -m pytest tests/test_storage.py
```

Run the storage migration Skill guard when applicable, using the Skill's actual directory/path instructions.

Tests MUST remain local/fixture-only; storage verification must not require provider APIs, credentials, exchanges, explorers, or RPC access.

## Completion criteria

A storage change is complete only when fresh init, repeated init, prior-version migration, preservation, accessor round-trip behavior, and relevant recovery/failure paths are verified for the changed contract, followed by applicable repository-wide gates.
