"""Command-line access to deterministic dataset profiles."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from .profile import build_dataset_profile, write_dataset_profile
from .snapshot import DatasetPolicy, DatasetSnapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile one read-only local dataset")
    parser.add_argument("database")
    parser.add_argument("--output", required=True, help="directory for immutable profile artifacts")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--label-horizon", action="append", default=[])
    args = parser.parse_args()
    parse_time = lambda value: datetime.fromisoformat(value) if value else None
    dataset = DatasetSnapshot.from_duckdb(args.database, DatasetPolicy(
        timeframe=args.timeframe, sources=tuple(args.source), start=parse_time(args.start), end=parse_time(args.end)))
    profile = build_dataset_profile(dataset, label_horizons=tuple(args.label_horizon))
    path = write_dataset_profile(profile, args.output)
    print(json.dumps({"profile_identity": profile["profile_identity"], "path": str(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
