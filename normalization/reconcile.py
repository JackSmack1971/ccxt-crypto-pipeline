"""Cross-source identity reconciliation and local data-quality reporting."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

from storage.db import connect, log_run_end, log_run_start, read_lineage, safe_error_message


def _address_key(chain: str, address: str) -> str:
    value = address.strip()
    return value if chain.lower() == "solana" else value.lower()


def reconcile_assets(db_path: str, *, linked_at: datetime | None = None) -> list[dict[str, Any]]:
    """Link DEX assets to CEX assets whose published contract address matches."""
    connection = connect(db_path)
    run_id = log_run_start("normalization_reconcile", connection=connection)
    linked_at = linked_at or datetime.now(timezone.utc)
    try:
        dex_assets = connection.execute(
            """SELECT canonical_id, chain_or_exchange, symbol_or_contract
               FROM assets WHERE source_type = 'dex' AND symbol_or_contract IS NOT NULL"""
        ).fetchall()
        cex_assets = connection.execute(
            """SELECT canonical_id, contract_address
               FROM assets WHERE source_type = 'cex' AND contract_address IS NOT NULL"""
        ).fetchall()
        by_address: dict[str, list[str]] = {}
        for canonical, address in cex_assets:
            if isinstance(address, str) and address.strip():
                for key in {address.strip(), address.strip().lower()}:
                    by_address.setdefault(key, []).append(canonical)
        links = []
        for dex_id, chain, address in dex_assets:
            if not isinstance(address, str) or not address.strip():
                continue
            candidates = by_address.get(_address_key(chain, address), [])
            if len(candidates) != 1:
                continue
            cex_id = candidates[0]
            connection.execute(
                """INSERT INTO lineage (dex_canonical_id, cex_canonical_id, linked_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT (dex_canonical_id, cex_canonical_id) DO UPDATE SET linked_at = excluded.linked_at""",
                [dex_id, cex_id, linked_at],
            )
            links.append({"dex_canonical_id": dex_id, "cex_canonical_id": cex_id,
                          "linked_at": linked_at})
        log_run_end(run_id, "success", connection=connection, rows_written=len(links))
        return links
    except Exception as exc:
        log_run_end(run_id, "failed", connection=connection, error_message=safe_error_message(exc))
        raise
    finally:
        connection.close()


def data_quality_report(db_path: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Return null, duplicate, and timestamp-sanity counts for every canonical table."""
    now = now or datetime.now(timezone.utc)
    connection = connect(db_path)
    try:
        tables = ("assets", "ohlcv", "events", "metadata", "runs", "lineage")
        columns_by_table = {
            table: tuple(row[1] for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall())
            for table in tables
        }
        nulls = {}
        for table, columns in columns_by_table.items():
            nulls[table] = {column: connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL"
            ).fetchone()[0] for column in columns}

        duplicate_queries = {
            "assets": "canonical_id",
            "ohlcv": "canonical_id, timestamp, timeframe",
            "events": "canonical_id, event_type, timestamp, source",
            "metadata": "canonical_id",
            "runs": "run_id",
            "lineage": "dex_canonical_id, cex_canonical_id",
        }
        duplicates = {}
        for table, keys in duplicate_queries.items():
            duplicates[table] = connection.execute(
                f"SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) n FROM {table} GROUP BY {keys})"
            ).fetchone()[0]

        timestamp_columns = {"assets": ("first_seen",), "ohlcv": ("timestamp",),
                             "events": ("timestamp",), "metadata": ("last_updated",),
                             "runs": ("started_at", "finished_at"), "lineage": ("linked_at",)}
        future = {table: {column: connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} > ?", [now]
        ).fetchone()[0] for column in columns} for table, columns in timestamp_columns.items()}
        prelaunch = {
            "ohlcv": connection.execute(
                """SELECT COUNT(*) FROM ohlcv o JOIN assets a USING (canonical_id)
                   WHERE o.timestamp < a.first_seen"""
            ).fetchone()[0],
            "events": connection.execute(
                """SELECT COUNT(*) FROM events e JOIN assets a USING (canonical_id)
                   WHERE e.timestamp < a.first_seen"""
            ).fetchone()[0],
            "metadata": connection.execute(
                """SELECT COUNT(*) FROM metadata m JOIN assets a USING (canonical_id)
                   WHERE m.last_updated < a.first_seen"""
            ).fetchone()[0],
        }
        return {"null_counts": nulls, "duplicate_counts": duplicates,
                "future_timestamp_counts": future, "prelaunch_counts": prelaunch}
    finally:
        connection.close()


def daily_ingestion_summary(db_path: str) -> list[dict[str, Any]]:
    """Summarize completed ingestion rows by UTC day, source, and job."""
    connection = connect(db_path)
    try:
        rows = connection.execute(
            """SELECT CAST(started_at AS DATE) AS day,
                      CASE WHEN instr(job_name, ':') > 0 THEN split_part(job_name, ':', 1)
                           ELSE job_name END AS source,
                      job_name, SUM(rows_written) AS rows_ingested
               FROM runs WHERE status = 'success'
               GROUP BY day, source, job_name ORDER BY day, source, job_name"""
        ).fetchall()
        return [{"day": day, "source": source, "job_name": job, "rows_ingested": count}
                for day, source, job, count in rows]
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="storage/pipeline.duckdb")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        print({"lineage": read_lineage(args.db), "quality": data_quality_report(args.db),
                "daily": daily_ingestion_summary(args.db)})
    else:
        print(reconcile_assets(args.db))


if __name__ == "__main__":
    main()
