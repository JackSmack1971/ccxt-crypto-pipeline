"""Run the local Phase 1 scheduler."""

from __future__ import annotations

import argparse

from .pipeline import Pipeline, build_scheduler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run one complete cycle and exit")
    parser.add_argument("--db", "--db-path", default="storage/pipeline.duckdb")
    args = parser.parse_args()
    pipeline = Pipeline(db_path=args.db)
    if args.once:
        for job in pipeline.run_cycle().jobs:
            print(f"{job.job_name}: {job.status} rows={job.rows_written}"
                  + (f" error={job.error}" if job.error else ""))
        return
    pipeline.run_cycle()
    build_scheduler(pipeline).start()


if __name__ == "__main__":
    main()
