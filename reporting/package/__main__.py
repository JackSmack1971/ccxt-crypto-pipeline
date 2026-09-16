"""Inspect and record immutable research/report review history."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .catalog import catalog_artifacts
from .export import export_package
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
    catalog = commands.add_parser("catalog")
    catalog.add_argument("--research-root")
    catalog.add_argument("--package-root")
    catalog.add_argument("--history-dir")
    catalog.add_argument("--query")
    export = commands.add_parser("export")
    export.add_argument("--package", required=True)
    export.add_argument("--history-dir", required=True)
    export.add_argument("--output-root", required=True)
    args = parser.parse_args()
    if args.command == "record":
        path = record_review(args.target, args.history_dir, target_kind=args.target_kind,
                             decision=args.decision, reviewer=args.reviewer,
                             reviewed_at=args.reviewed_at, rationale=args.rationale,
                             notes=args.notes, supersedes_review_id=args.supersedes_review_id)
        result = {"review_id": path.stem, "path": str(path)}
    elif args.command == "show":
        result = list(review_history(args.history_dir, args.target_id))
    elif args.command == "catalog":
        result = [asdict(item) for item in catalog_artifacts(
            research_root=args.research_root, package_root=args.package_root,
            history_dir=args.history_dir, query=args.query)]
    else:
        path = export_package(args.package, args.history_dir, args.output_root)
        result = {"export_id": path.name, "path": str(path)}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        raise SystemExit(1)
