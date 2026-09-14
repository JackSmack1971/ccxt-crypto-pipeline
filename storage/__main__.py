"""Run storage initialization and two-store recovery: python -m storage <database-path> [options]."""

import argparse
import json

from .db import init_db, repair_parquet_publication, verify_parquet_publication


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize canonical DuckDB storage and check/repair Parquet publication")
    parser.add_argument("database", help="DuckDB file to initialize")
    parser.add_argument("--parquet-dir", help="Parquet publication root (default: <database directory>/parquet)")
    parser.add_argument("--verify-parquet", action="store_true",
                        help="report OHLCV Parquet partitions that diverge from DuckDB without changing them")
    parser.add_argument("--repair-parquet", action="store_true",
                        help="deterministically rebuild any OHLCV Parquet partitions that diverge from DuckDB")
    args = parser.parse_args()

    init_db(args.database)

    if args.verify_parquet:
        divergent = verify_parquet_publication(args.database, parquet_dir=args.parquet_dir)
        print(json.dumps([{**item, "partition_date": item["partition_date"].isoformat()}
                          for item in divergent], indent=2))
    if args.repair_parquet:
        repaired = repair_parquet_publication(args.database, parquet_dir=args.parquet_dir)
        print(json.dumps([{**item, "partition_date": item["partition_date"].isoformat()}
                          for item in repaired], indent=2))


if __name__ == "__main__":
    main()
