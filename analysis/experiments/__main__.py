"""Validate, run, inspect, or approve local governed experiments."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from analysis.datasets import DatasetPolicy, DatasetSnapshot

from .control import (approve_experiment_run, execute_experiment, inspect_experiment_run,
                      load_experiment_spec, validate_experiment_spec)
from .research import (ResearchRegistry, research_hypothesis_from_dict,
                       research_question_from_dict, hypothesis_identity, question_identity, write_registry)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a JSON experiment spec")
    validate.add_argument("spec")
    run = commands.add_parser("run", help="run a spec against canonical local storage")
    run.add_argument("spec"); run.add_argument("--db", required=True); run.add_argument("--output", required=True)
    run.add_argument("--timeframe", default="1d"); run.add_argument("--source", action="append", default=[])
    run.add_argument("--parquet-dir")
    inspect = commands.add_parser("inspect", help="verify and inspect an immutable run")
    inspect.add_argument("run_dir")
    approve = commands.add_parser("approve", help="record a separate human approval attestation")
    approve.add_argument("run_dir"); approve.add_argument("--approval-dir", required=True)
    approve.add_argument("--reviewer", required=True); approve.add_argument("--reviewed-at", required=True)
    approve.add_argument("--rationale", required=True)
    question = commands.add_parser("validate-question", help="validate and identify a research question")
    question.add_argument("path")
    hypothesis = commands.add_parser("validate-hypothesis", help="validate and identify a research hypothesis")
    hypothesis.add_argument("path")
    registry = commands.add_parser("write-registry", help="write an immutable research registry")
    registry.add_argument("path", help="JSON object with questions and hypotheses arrays")
    registry.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.command == "validate":
        result = {"experiment_spec_id": validate_experiment_spec(args.spec), "valid": True}
    elif args.command == "run":
        spec = load_experiment_spec(args.spec)
        policy = DatasetPolicy(timeframe=args.timeframe, sources=tuple(args.source))
        snapshot = DatasetSnapshot.from_duckdb(args.db, policy, parquet_dir=args.parquet_dir)
        path = execute_experiment(spec, snapshot, args.output)
        result = {"run_id": path.name, "path": str(path)}
    elif args.command == "inspect":
        result = asdict(inspect_experiment_run(args.run_dir)); result["path"] = str(result["path"])
    elif args.command == "approve":
        path = approve_experiment_run(args.run_dir, args.approval_dir, reviewer=args.reviewer,
                                      reviewed_at=args.reviewed_at, rationale=args.rationale)
        result = {"approval_id": path.stem, "path": str(path)}
    elif args.command == "validate-question":
        question = research_question_from_dict(json.loads(Path(args.path).read_text(encoding="utf-8")))
        result = {"question_id": question.question_id, "identity": question_identity(question), "valid": True}
    elif args.command == "validate-hypothesis":
        hypothesis = research_hypothesis_from_dict(json.loads(Path(args.path).read_text(encoding="utf-8")))
        result = {"hypothesis_id": hypothesis.hypothesis_id, "identity": hypothesis_identity(hypothesis), "valid": True}
    else:
        payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
        questions = tuple(research_question_from_dict(item) for item in payload.get("questions", ()))
        hypotheses = tuple(research_hypothesis_from_dict(item) for item in payload.get("hypotheses", ()))
        path = write_registry(ResearchRegistry(questions, hypotheses), args.output)
        result = {"registry_id": path.parent.name, "path": str(path)}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
