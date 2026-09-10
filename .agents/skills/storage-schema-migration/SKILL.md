---
name: storage-schema-migration
description: Evolve the local `/storage/` persistence contract when adding, removing, renaming, or changing DuckDB tables/columns/constraints, Parquet fields or partitioning, or persisted event/risk-flag types. Use for storage schema migrations that must bump `SCHEMA_VERSION`, migrate existing data safely, keep idempotent initialization and `storage/db.py` accessors synchronized, and validate with fixture-only tests. Do not use for ingestion/API-client work, live provider integration tests, analytics-only query changes, or storage reads that do not change the persisted contract.
---

# Storage Schema Migration

Evolve the persisted DuckDB/Parquet contract without schema drift, silent data loss, or network-dependent tests.

## Authority and scope

Treat the user's current request and repository-local storage contracts as authoritative for the target version. Use [references/storage-contract.md](references/storage-contract.md) as the Phase 1 baseline and invariant checklist, not as permission to overwrite a newer repository schema.

Read [references/migration-evidence.md](references/migration-evidence.md) when the change touches existing DuckDB data, Parquet schema/partitioning, destructive operations, or migration verification.

Own only persisted-contract changes. If inspection shows no table/column/constraint, Parquet physical schema/partitioning, or persisted event/risk vocabulary change, stop using this workflow and continue with the neighboring task instead.

## Workflow

### 1. Establish the pre-change baseline

Before editing:

- Inspect `git status` and choose the comparison base that represents the pre-migration state. Do not overwrite unrelated work.
- Locate the single authoritative `SCHEMA_VERSION`, schema/init code, `storage/db.py`, storage tests, Parquet readers/writers, and any canonical event/risk-flag definitions.
- Inspect call sites of affected accessors and persisted fields before changing their contract.
- Run the narrow existing storage tests when practical. Record failures that already exist so they are not attributed to the migration.
- Classify the migration as one or more of: DuckDB catalog change, Parquet schema/partition change, persisted vocabulary change.

If the current schema/version source is ambiguous or duplicated, resolve that architecture conflict before implementing the migration. Do not create a second authority.

### 2. Define the target and migration path

For every persisted-contract change:

- Advance the authoritative `SCHEMA_VERSION` for this migration unit according to the repository's existing version convention. The target value must be newer than the chosen pre-change base; do not invent gratuitous intermediate versions unless the repository's migration framework requires them.
- Make fresh initialization create the complete target schema and remain idempotent when run repeatedly.
- Make an already-initialized store at the prior supported version converge to the same target schema without losing existing rows.
- Do not treat `CREATE TABLE IF NOT EXISTS` as an existing-database migration for a changed table; it leaves an existing table unchanged.
- Preserve data by default. Do not drop/recreate data-bearing DuckDB tables, rewrite/delete Parquet partitions, or perform another destructive conversion without explicit authorization when user data could be lost.
- Prefer a reversible/transactional migration where the repository and DuckDB operation support it. When dependencies or unsupported alterations prevent an in-place change, use a copy/validate/swap or equivalent safe strategy and prove preservation before cleanup.

For persisted event or risk-flag vocabulary changes, treat the vocabulary as part of the schema contract even when the physical SQL type remains `VARCHAR` or JSON. Update the canonical definition/normalization path, bump the schema version, and define behavior for legacy and unknown values rather than silently coercing them.

For Parquet changes, explicitly choose how old and new partitions coexist. Either make readers safely reconcile compatible schemas, backfill/rewrite existing files, or use another repository-supported evolution strategy. Do not leave mixed-schema behavior implicit.

### 3. Synchronize the access layer

Reconcile `storage/db.py` with the target schema:

- Check every affected insert, upsert, read helper, explicit column list, parameter ordering, serializer/deserializer, conflict key, and returned row shape.
- Search downstream callers for assumptions about tuple/dict shape, required fields, defaults, and enum/vocabulary values.
- Update accessors when the contract changes. If no `db.py` edit is necessary, prove compatibility with a round-trip test covering the changed contract; do not merely assert that it is unaffected.
- Keep storage logic free of ingestion/provider concerns. Do not add API calls, credentials, provider clients, or network fallbacks to make a storage test pass.

### 4. Build fixture-only migration tests

All tests for this skill must be local and deterministic. Use temporary DuckDB files/directories and local fixture data only.

For each applicable branch, test:

- fresh database initialization reaches the target schema;
- running initialization again is harmless and leaves the same schema/data;
- a prior-version database fixture migrates to the target;
- existing representative rows survive with matching values;
- affected `storage/db.py` writes and reads round-trip the new contract;
- event/risk vocabulary accepts, preserves, rejects, or maps values exactly as the repository contract specifies;
- old and new Parquet partitions remain queryable together, or the chosen rewrite/backfill produces a uniform verified schema;
- failure mid-migration rolls back or leaves a recoverable state when the chosen mechanism can fail partway through.

**Prohibited:** real external API calls, live RPC/explorer calls, `ccxt` exchange calls, HTTP integration checks, production credentials, or tests whose success depends on internet availability. Mocking is not a reason to introduce provider integration into this layer; prefer direct fixture inputs at the storage boundary.

### 5. Verify with independent evidence

Run the bundled guard from the skill directory, selecting the correct Git base:

```bash
python scripts/storage_migration_guard.py --repo <repo-root> --base-ref HEAD
```

If the migration is already committed, compare against the parent or merge base instead of blindly using `HEAD`.

When practical, create one fresh target DB and one DB upgraded from the prior schema, then compare their catalog signatures:

```bash
python scripts/storage_migration_guard.py --repo <repo-root> --base-ref <pre-migration-ref> --fresh-db <fresh-db-path> --migrated-db <migrated-db-path>
```

Treat guard warnings as prompts for explicit inspection, not automatic proof of failure or success. The script mechanically checks version movement, changed test presence, obvious live-network calls in changed Python tests, `storage/db.py` presence/synchronization signals, and optional fresh-vs-migrated DuckDB schema convergence. If Git/Python or the project's DuckDB dependency is unavailable, use equivalent repository-native evidence where possible and report the guard or catalog comparison as `UNVERIFIED`; do not silently claim it passed.

Then run the narrow migration/storage tests and the smallest broader suite that covers affected callers. Inspect the final diff for accidental generated data, local DB files, Parquet fixtures outside test temp paths, secrets, or unrelated edits.

## Completion contract

Declare success only when all applicable evidence exists:

- `SCHEMA_VERSION` advanced from the pre-change base according to the repository convention;
- fresh init and repeated init both pass;
- prior-version fixture migration passes and preserves data;
- fresh and migrated schemas converge on the same intended catalog shape;
- `storage/db.py` and affected callers are synchronized, proven by round-trip tests;
- Parquet compatibility/rewrite evidence exists when Parquet changed;
- event/risk vocabulary compatibility behavior is tested when vocabulary changed;
- all storage-layer tests are fixture-only with no real external API calls;
- targeted tests pass, pre-existing failures are distinguished, and no new relevant failure remains;
- final diff contains no destructive or unrelated change lacking authorization.

If any required evidence cannot be obtained, report the migration as blocked or inconclusive with the missing evidence. Do not weaken the acceptance criteria or substitute a live integration test.
