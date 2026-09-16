"""Inspect and record immutable research/report review history."""

from __future__ import annotations

import argparse
import json

from .review_history import record_review, review_history


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record")
    record.add_argument("target"); record.add_argument("--target-kind", required=True,
                        choices=("research_run", "package")); record.add_argument("--history-dir", required=True)
    record.add_argument("--decision", required=True, choices=("approved", "rejected", "superseded", "note"))
    record.add_argument("--reviewer", required=True); record.add_argument("--reviewed-at", required=True)
    record.add_argument("--rationale", default=""); record.add_argument("--notes", default="")
    record.add_argument("--supersedes-review-id")
    show = commands.add_parser("show")
    show.add_argument("target_id"); show.add_argument("--history-dir", required=True)
    args = parser.parse_args()
    if args.command == "record":
        path = record_review(args.target, args.history_dir, target_kind=args.target_kind,
                             decision=args.decision, reviewer=args.reviewer,
                             reviewed_at=args.reviewed_at, rationale=args.rationale,
                             notes=args.notes, supersedes_review_id=args.supersedes_review_id)
        result = {"review_id": path.stem, "path": str(path)}
    else:
        result = list(review_history(args.history_dir, args.target_id))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
