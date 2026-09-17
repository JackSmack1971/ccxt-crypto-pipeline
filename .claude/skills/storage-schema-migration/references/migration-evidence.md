# Migration strategy and evidence notes

Read this reference only when choosing or validating a DuckDB/Parquet migration strategy.

## DuckDB existing-table behavior

`CREATE TABLE IF NOT EXISTS` does nothing when the table already exists. Therefore changing the fresh-create DDL alone cannot migrate an existing table. Existing stores need an explicit evolution path.

DuckDB `ALTER TABLE` changes existing catalog schema and follows transactional semantics, but some alterations can be blocked by dependencies. For incompatible/destructive transformations, prefer a safe copy/validate/swap pattern rather than erasing the original before verification.

Relevant official documentation:

- https://duckdb.org/docs/current/sql/statements/create_table
- https://duckdb.org/docs/current/sql/statements/alter_table
- https://duckdb.org/docs/current/sql/meta/duckdb_table_functions

## Parquet schema evolution

DuckDB's `read_parquet` defaults `union_by_name` to `false`. When multiple Parquet files have compatible but different schemas, `union_by_name = true` can reconcile columns by name and fills missing fields with `NULL`.

That is a strategy, not an automatic requirement. Choose among:

1. **Read-compatible evolution** — old and new files remain; readers explicitly reconcile schemas and downstream code handles missing legacy values.
2. **Backfill/rewrite** — rewrite old partitions to the target schema, verify counts/content/schema, then replace originals only after successful validation.
3. **Repository-native evolution mechanism** — use it when the project already defines a stronger contract.

If partition keys or path layout change, schema union alone is insufficient; test discovery, pruning/filtering assumptions, and path compatibility explicitly.

Relevant official documentation:

- https://duckdb.org/docs/stable/data/parquet/overview
- https://duckdb.org/2025/01/10/union-by-name

## Minimum evidence matrix

| Change | Fresh init | Re-init | Prior-version upgrade | Data preservation | `db.py` round trip | Extra evidence |
|---|---|---|---|---|---|---|
| Add DuckDB table | required | required | required | required for existing tables | required | table/constraints present after upgrade |
| Add/rename/change column | required | required | required | required | required | defaults/nullability/legacy values verified |
| Constraint/key change | required | required | required | required | required | constraint metadata and conflict behavior verified |
| OHLCV Parquet field change | required where catalog/view affected | required | required | required | required | old+new partition compatibility or verified rewrite |
| Parquet partition-layout change | required | required | required | required | required | path discovery and partition predicates verified |
| Event/risk vocabulary change | version required | re-init if init owns vocabulary | legacy compatibility required | existing values preserved/mapped | affected helpers required | accepted/rejected/unknown behavior explicit |

## Destructive-change boundary

Treat dropping columns/tables, type narrowing, lossy value mapping, and Parquet rewrites/deletions as higher-risk than additive changes. Before any action that can irreversibly discard user data:

- inspect actual stored data and dependencies;
- define the conversion and rollback path;
- validate on a copy/temporary store;
- obtain explicit authorization when the operation would delete or overwrite real data;
- verify the replacement before removing the recoverable original.

## Completion calibration

Passing a fresh-create test is insufficient. The strongest migration proof is convergence: a fresh target DB and a DB upgraded from the prior supported version expose the same intended schema signature, while representative pre-existing data survives and affected accessors still round-trip correctly.
