"""Print a machine-readable health summary for the local pipeline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from storage.db import read_runs


def health_report(db_path: str = "storage/pipeline.duckdb") -> dict:
    runs = sorted(
        read_runs(db_path),
        key=lambda run: (run["started_at"] or datetime.min,
                         run["finished_at"] or datetime.min,
                         run["run_id"]),
    )
    latest = {}
    counts = {}
    for run in runs:
        latest[run["job_name"]] = run
        counts[run["status"]] = counts.get(run["status"], 0) + 1
    return {"database": db_path, "run_count": len(runs), "status_counts": counts,
            "healthy": not any(run["status"] in {"failed", "running"} for run in runs),
            "latest_by_job": latest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", "--db-path", default="storage/pipeline.duckdb")
    args = parser.parse_args()
    print(json.dumps(health_report(args.db), default=str, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
