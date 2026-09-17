"""Deterministic Phase 6 experiment execution.

This module is the first slice that actually executes an ``ExperimentSpec``.
It composes only the already-governed Phase 3 helpers
(``extract_cohort``, ``compute_features``, ``generate_labels``, ``build_split``,
``score_candidate``, ``baseline_families``, ``evaluate_candidate_promotion``)
in the sequence the spec declares, against one local, already-loaded
``DatasetSnapshot``. It never redefines cohort, feature, label, split, or
candidate-evaluation semantics, and it never fabricates statistical
significance evidence. It freezes the complete multiplicity family before
evaluation, while unavailable raw p-values remain explicitly unavailable.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from analysis.alpha import (FeatureRegistry, PromotionEvidence, baseline_families, build_split,
                            compute_features, evaluate_candidate_promotion, extract_cohort,
                            feature_definition_id, feature_policy_versions, generate_labels,
                            label_definition_id, resolve_feature_definition, score_candidate,
                            validate_temporal_alignment)
from analysis.datasets.snapshot import DatasetSnapshot

from .spec import ExperimentSpec, experiment_spec_dict, experiment_spec_id
from .hypotheses import (FrozenHypothesisFamily, evaluate_hypothesis_family,
                         freeze_hypothesis_family)
from .significance import (SIGNIFICANCE_MANIFEST_VERSION, SignificanceEvidenceBundle,
                           build_significance_evidence_bundle)
from .walk_forward import build_walk_forward_evaluation
from .uncertainty import bootstrap_mean
from .stress import _build_stress_matrix
from .stability import build_stability_evidence
from .negative_controls import build_negative_control_evidence
from .closure import build_validation_closure
from .falsification import build_falsification_evidence

MANIFEST_VERSION = "phase8r-run-v2"


def _validate_significance_temporal_boundary(bundle: SignificanceEvidenceBundle,
                                             split: Any) -> None:
    """Keep supplied significance evidence within its eligible partition."""
    def parse(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    boundaries = {item["name"]: item["timestamp"] for item in split.boundaries}
    try:
        observed_through = parse(bundle.entries[0].observed_through)
    except (AttributeError, ValueError) as exc:
        raise ValueError("invalid significance evidence temporal boundary") from exc

    if bundle.stage == "discovery":
        boundary_name = "discovery_validation"
        boundary = boundaries.get(boundary_name)
        if boundary is None:
            raise ValueError("discovery significance evidence requires a discovery/validation boundary")
        if observed_through > parse(boundary):
            raise ValueError(
                "discovery significance evidence observed after the discovery/validation boundary")
    elif bundle.stage == "confirmation":
        boundary_name = "validation_holdout"
        boundary = boundaries.get(boundary_name)
        if boundary is None:
            raise ValueError("confirmation significance evidence requires a validation/holdout boundary")
        if observed_through < parse(boundary):
            raise ValueError(
                "confirmation significance evidence observed before the validation/holdout boundary")


def resolve_feature_registry(spec: ExperimentSpec) -> FeatureRegistry:
    """Resolve the spec's declared feature identities to canonical, versioned
    definitions through the durable ``analysis/alpha/registry.py`` catalog.

    ``ExperimentSpec`` already rejects an unresolved feature identity at
    construction time, so every name here is guaranteed to have a version in
    the spec's declared policy; this stays a defensive re-check rather than
    the sole gate.
    """
    versions = feature_policy_versions(spec.feature_policy_version)
    unsupported = sorted(set(spec.feature_set) - set(versions))
    if unsupported:
        raise ValueError(f"unsupported experiment feature identity: {', '.join(unsupported)}")
    registry = FeatureRegistry()
    for name in spec.feature_set:
        registry.register(resolve_feature_definition(
            name, versions[name], lookback=timedelta(seconds=spec.split.feature_lookback_seconds)))
    return registry


_SELECTION_RULE = re.compile(r"^(?P<feature>[A-Za-z0-9_]+)(?P<op>>=|<=|==|>|<)p(?P<pct>\d{1,3})$")
_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">=": lambda value, threshold: value >= threshold,
    "<=": lambda value, threshold: value <= threshold,
    ">": lambda value, threshold: value > threshold,
    "<": lambda value, threshold: value < threshold,
    "==": lambda value, threshold: value == threshold,
}


def _parse_selection_rule(rule: str) -> tuple[str, str, float]:
    match = _SELECTION_RULE.match(rule.strip())
    if not match:
        raise ValueError(f"unsupported candidate selection rule: {rule}")
    pct = float(match.group("pct"))
    if not (0 <= pct <= 100):
        raise ValueError(f"selection rule percentile out of range: {rule}")
    return match.group("feature"), match.group("op"), pct


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100) * (len(ordered) - 1)
    lower, upper = math.floor(rank), math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def _selection_threshold(feature_rows: tuple[dict[str, Any], ...], rule: str) -> tuple[str, str, float | None]:
    feature_name, operator, pct = _parse_selection_rule(rule)
    if feature_name not in {"launch_liquidity_usd", "lookback_return"}:
        raise ValueError(f"unsupported candidate selection feature: {feature_name}")
    available = [(row["token_id"], row.get(feature_name)) for row in feature_rows]
    numeric_values = [value for _, value in available if isinstance(value, (int, float)) and math.isfinite(value)]
    if not numeric_values:
        return feature_name, operator, None
    return feature_name, operator, _percentile(numeric_values, pct)


def _select_token_ids(feature_rows: tuple[dict[str, Any], ...], feature_name: str,
                      operator: str, threshold: float | None) -> frozenset[str]:
    if threshold is None:
        return frozenset()
    compare = _OPERATORS[operator]
    return frozenset(row["token_id"] for row in feature_rows
                     for value in (row.get(feature_name),)
                     if isinstance(value, (int, float)) and math.isfinite(value) and compare(value, threshold))


def _selected_token_ids(feature_rows: tuple[dict[str, Any], ...], rule: str) -> frozenset[str]:
    """Resolve a declarative selection rule within one partition.

    This helper is retained for the discovery-only callers. Sequential runner
    stages learn the threshold once from discovery and call
    ``_select_token_ids`` with that frozen threshold for later partitions.
    """
    feature_name, operator, threshold = _selection_threshold(feature_rows, rule)
    return _select_token_ids(feature_rows, feature_name, operator, threshold)


def _enrich_uncertainty(candidate: Any, selected_labels: tuple[Any, ...], spec: ExperimentSpec) -> tuple[Any, dict[str, Any]]:
    uncertainty = {**bootstrap_mean((label.value for label in selected_labels), spec.uncertainty),
                   "scope": "selected_candidate_observations",
                   "candidate": {"name": spec.candidate.name, "horizon": spec.candidate.horizon,
                                 "selected_token_ids": sorted(label.token_id for label in selected_labels)}}
    return replace(candidate, uncertainty={
        **candidate.uncertainty,
        "standard_ci95_low": candidate.uncertainty["ci95_low"],
        "standard_ci95_high": candidate.uncertainty["ci95_high"],
        "ci95_low": uncertainty["ci95_low"], "ci95_high": uncertainty["ci95_high"],
        "method": uncertainty["method"], "policy": uncertainty["config"],
    }), uncertainty


def _promotion_evidence(candidate: Any, *, target_stage: str,
                        discovery_adjusted_p_value: float | None = None,
                        validation_replicated: bool | None = None,
                        validation_semantics_frozen: bool | None = None,
                        holdout_adjusted_p_value: float | None = None) -> PromotionEvidence:
    difference = candidate.baseline_comparison.get("difference")
    ci95_low = candidate.uncertainty.get("ci95_low")
    return PromotionEvidence(
        target_stage=target_stage,
        discovery_adjusted_p_value=discovery_adjusted_p_value,
        effect_size=difference,
        validation_replicated=validation_replicated,
        validation_semantics_frozen=validation_semantics_frozen,
        holdout_adjusted_p_value=holdout_adjusted_p_value,
        baseline_superior=difference is not None and difference > 0,
        uncertainty_supports_effect=ci95_low is not None and ci95_low > 0,
        cost_sensitivity_passed=bool(candidate.cost_sensitivity)
        and all(value is not None and value > 0 for value in candidate.cost_sensitivity.values()),
    )


def _candidate_hypothesis(family: FrozenHypothesisFamily, rule: str, horizon: str):
    feature, operator, percentile = _parse_selection_rule(rule)
    threshold = f"{operator}p{int(percentile)}"
    matches = tuple(item for item in family.hypotheses
                    if item.feature == feature and item.threshold == threshold
                    and item.horizon == horizon and item.subgroup is None)
    if len(matches) != 1:
        raise ValueError("candidate selection does not identify exactly one frozen hypothesis")
    return matches[0]


def _walk_forward_results(evaluation: Any, feature_rows: tuple[dict[str, Any], ...],
                          labels: tuple[Any, ...], spec: ExperimentSpec) -> dict[str, Any]:
    """Score each fold using a threshold learned from that fold's training data.

    Only validation labels are scored. Sealed-holdout rows are retained as
    membership evidence and are deliberately never passed to candidate or
    baseline evaluation here.
    """
    feature_name, operator, pct = _parse_selection_rule(spec.candidate.selection_rule)
    compare = _OPERATORS[operator]
    fold_results = []
    for fold in evaluation.folds:
        train_ids, validation_ids = frozenset(fold.train), frozenset(fold.validation)
        train_features = tuple(row for row in feature_rows if row["token_id"] in train_ids)
        numeric = [row.get(feature_name) for row in train_features
                   if isinstance(row.get(feature_name), (int, float))
                   and math.isfinite(row[feature_name])]
        threshold = _percentile(numeric, pct) if numeric else None
        validation_features = tuple(row for row in feature_rows if row["token_id"] in validation_ids)
        selected = frozenset(row["token_id"] for row in validation_features
                             if threshold is not None
                             and isinstance(row.get(feature_name), (int, float))
                             and math.isfinite(row[feature_name])
                             and compare(row[feature_name], threshold))
        validation_labels = tuple(row for row in labels if row.token_id in validation_ids)
        baselines = baseline_families(validation_labels, horizon=spec.candidate.horizon,
                                      feature_rows=validation_features)
        candidate = score_candidate(
            spec.candidate.name, validation_labels, horizon=spec.candidate.horizon,
            selected=lambda row: row.token_id in selected,
            baseline_mean=baselines["no_trade"]["mean_return"], turnover=spec.costs.turnover,
            costs=spec.costs.scenarios, min_coverage=spec.candidate.min_coverage)
        fold_results.append({"fold": fold.fold, "selection_threshold": threshold,
                             "selection_feature": feature_name, "baselines": baselines,
                             "candidate": candidate})
    return {**evaluation.as_dict(), "results": fold_results}


def _plain(value: Any) -> Any:
    if hasattr(value, "as_artifact"):
        return _plain(value.as_artifact())
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, frozenset, set)):
        return [_plain(item) for item in value]
    return value


_SECRET = re.compile(r"(?i)(api[_-]?key|password|secret|token|private[_-]?key|rpc[_-]?url)\s*[:=]\s*[^\s,;]+")
_URL_CREDENTIAL = re.compile(r"(?i)(://)[^/\s:@]+:[^/\s@]+@")


def _safe(value: Any) -> Any:
    value = _plain(value)
    if isinstance(value, dict):
        return {key: "[REDACTED]" if re.search(r"(?i)(api[_-]?key|password|secret|token|private[_-]?key|rpc[_-]?url)$", key)
                else _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, str):
        return _SECRET.sub(r"\1=[REDACTED]", _URL_CREDENTIAL.sub(r"\1[REDACTED]@", value))
    return value


def _dump(value: Any) -> bytes:
    return (json.dumps(_safe(value), default=str, sort_keys=True, separators=(",", ":")) + "\n").encode()


def run_experiment(spec: ExperimentSpec, snapshot: DatasetSnapshot, output_dir: str | Path,
                   significance_evidence: SignificanceEvidenceBundle | None = None, *,
                   confirmation_significance_evidence: SignificanceEvidenceBundle | None = None) -> Path:
    """Execute ``spec`` against ``snapshot`` and write one immutable run directory.

    The run identity is keyed by the spec's own content-addressed identity
    plus the dataset identity and code version, so identical inputs always
    resolve to the same run and a changed spec, dataset, or code version
    always produces a distinct one.
    """
    # Commit the family before any research result is inspected.
    hypothesis_family = freeze_hypothesis_family(spec)
    cohort = extract_cohort(snapshot, spec.cohort)
    split = build_split(cohort, embargo_days=spec.split.embargo_days,
                        feature_lookback=timedelta(seconds=spec.split.feature_lookback_seconds),
                        label_horizon=timedelta(seconds=spec.split.label_horizon_seconds))
    significance_bundle = None
    significance_evaluation = None
    candidate_adjusted_p_value = None
    if significance_evidence is not None:
        if significance_evidence.manifest_version != SIGNIFICANCE_MANIFEST_VERSION:
            raise ValueError("unsupported significance evidence manifest version")
        if significance_evidence.stage != "discovery":
            raise ValueError(
                "primary significance evidence must be discovery-stage; "
                "confirmation evidence requires confirmation_significance_evidence")
        significance_bundle = build_significance_evidence_bundle(
            hypothesis_family, significance_evidence.entries,
            stage=significance_evidence.stage, dataset_version=snapshot.dataset_identity)
        _validate_significance_temporal_boundary(significance_bundle, split)
        significance_evaluation = evaluate_hypothesis_family(
            hypothesis_family, significance_bundle.raw_p_values(), stage=significance_bundle.stage,
            dataset_version=snapshot.dataset_identity,
            date_tested=significance_bundle.entries[0].observed_through)
        candidate_hypothesis = _candidate_hypothesis(
            hypothesis_family, spec.candidate.selection_rule, spec.candidate.horizon)
        candidate_result = next(item for item in significance_evaluation.hypotheses
                                if (item.feature, item.threshold, item.horizon, item.subgroup,
                                    item.model_specification) == (
                                        candidate_hypothesis.feature, candidate_hypothesis.threshold,
                                        candidate_hypothesis.horizon, candidate_hypothesis.subgroup,
                                        candidate_hypothesis.model_specification))
        candidate_adjusted_p_value = candidate_result.adjusted_value
    registry = resolve_feature_registry(spec)
    feature_rows = compute_features(snapshot, cohort, registry)

    labels_by_horizon = {label.horizon: generate_labels(snapshot, cohort, label) for label in spec.labels}
    candidate_labels = labels_by_horizon[spec.candidate.horizon]
    validate_temporal_alignment(cohort, feature_rows, candidate_labels)

    walk_forward = None
    if spec.split.evaluation_mode == "walk_forward":
        walk_forward = build_walk_forward_evaluation(
            cohort, folds=spec.split.walk_forward_folds, embargo_days=spec.split.embargo_days,
            feature_lookback=timedelta(seconds=spec.split.feature_lookback_seconds),
            label_horizon=timedelta(seconds=spec.split.label_horizon_seconds))

    discovery_ids = frozenset(split.discovery)
    discovery_features = tuple(row for row in feature_rows if row["token_id"] in discovery_ids)
    discovery_labels = tuple(row for row in candidate_labels if row.token_id in discovery_ids)

    selection_feature, selection_operator, selection_threshold = _selection_threshold(
        discovery_features, spec.candidate.selection_rule)
    selected_ids = _select_token_ids(discovery_features, selection_feature,
                                     selection_operator, selection_threshold)
    baselines = baseline_families(discovery_labels, horizon=spec.candidate.horizon, feature_rows=discovery_features)
    candidate = score_candidate(spec.candidate.name, discovery_labels, horizon=spec.candidate.horizon,
                                selected=lambda row: row.token_id in selected_ids,
                                baseline_mean=baselines["no_trade"]["mean_return"],
                                turnover=spec.costs.turnover, costs=spec.costs.scenarios,
                                min_coverage=spec.candidate.min_coverage)
    selected_labels = tuple(label for label in discovery_labels if label.token_id in selected_ids
                            and label.status == "COMPLETE" and label.value is not None)
    candidate, uncertainty = _enrich_uncertainty(candidate, selected_labels, spec)

    discovery_evidence = _promotion_evidence(
        candidate, target_stage="discovery",
        discovery_adjusted_p_value=(candidate_adjusted_p_value
                                    if significance_bundle is not None
                                    and significance_bundle.stage == "discovery" else None))
    decision = evaluate_candidate_promotion(candidate, discovery_evidence, spec.promotion_policy)
    stage_records: list[dict[str, Any]] = [{
        "stage": "discovery", "selection_threshold": selection_threshold,
        "selected_token_ids": sorted(selected_ids), "candidate": candidate, "promotion": decision,
    }]
    validation_candidate = None
    holdout_candidate = None
    confirmation_bundle = None
    confirmation_evaluation = None

    # A later partition is scored only after the preceding governed decision
    # succeeds. The discovery-learned threshold, not a later-partition
    # percentile, defines the candidate in every subsequent stage.
    if decision.state == "discovery_promoted":
        validation_ids = frozenset(split.validation)
        validation_features = tuple(row for row in feature_rows if row["token_id"] in validation_ids)
        validation_labels = tuple(row for row in candidate_labels if row.token_id in validation_ids)
        validation_selected_ids = _select_token_ids(
            validation_features, selection_feature, selection_operator, selection_threshold)
        validation_baselines = baseline_families(
            validation_labels, horizon=spec.candidate.horizon, feature_rows=validation_features)
        validation_candidate = score_candidate(
            spec.candidate.name, validation_labels, horizon=spec.candidate.horizon,
            selected=lambda row: row.token_id in validation_selected_ids,
            baseline_mean=validation_baselines["no_trade"]["mean_return"],
            turnover=spec.costs.turnover, costs=spec.costs.scenarios,
            min_coverage=spec.candidate.min_coverage)
        validation_selected_labels = tuple(
            label for label in validation_labels if label.token_id in validation_selected_ids
            and label.status == "COMPLETE" and label.value is not None)
        validation_candidate, _ = _enrich_uncertainty(
            validation_candidate, validation_selected_labels, spec)
        validation_replicated = (
            validation_candidate.baseline_comparison.get("difference") is not None
            and validation_candidate.baseline_comparison["difference"] > 0)
        validation_evidence = _promotion_evidence(
            validation_candidate, target_stage="validation",
            discovery_adjusted_p_value=candidate_adjusted_p_value,
            validation_replicated=validation_replicated,
            validation_semantics_frozen=split.sealed and selection_threshold is not None)
        decision = evaluate_candidate_promotion(
            validation_candidate, validation_evidence, spec.promotion_policy)
        stage_records.append({
            "stage": "validation", "selection_threshold": selection_threshold,
            "selected_token_ids": sorted(validation_selected_ids), "candidate": validation_candidate,
            "promotion": decision,
        })

    if decision.state == "validation_confirmed":
        if confirmation_significance_evidence is not None:
            if confirmation_significance_evidence.manifest_version != SIGNIFICANCE_MANIFEST_VERSION:
                raise ValueError("unsupported confirmation significance evidence manifest version")
            confirmation_bundle = build_significance_evidence_bundle(
                hypothesis_family, confirmation_significance_evidence.entries,
                stage="confirmation", dataset_version=snapshot.dataset_identity)
            _validate_significance_temporal_boundary(confirmation_bundle, split)
            confirmation_evaluation = evaluate_hypothesis_family(
                hypothesis_family, confirmation_bundle.raw_p_values(), stage="confirmation",
                dataset_version=snapshot.dataset_identity,
                date_tested=confirmation_bundle.entries[0].observed_through)
            candidate_hypothesis = _candidate_hypothesis(
                hypothesis_family, spec.candidate.selection_rule, spec.candidate.horizon)
            holdout_adjusted_p_value = next(
                item.adjusted_value for item in confirmation_evaluation.hypotheses
                if (item.feature, item.threshold, item.horizon, item.subgroup,
                    item.model_specification) == (
                        candidate_hypothesis.feature, candidate_hypothesis.threshold,
                        candidate_hypothesis.horizon, candidate_hypothesis.subgroup,
                        candidate_hypothesis.model_specification))
        else:
            holdout_adjusted_p_value = None

        holdout_ids = frozenset(split.holdout)
        holdout_features = tuple(row for row in feature_rows if row["token_id"] in holdout_ids)
        holdout_labels = tuple(row for row in candidate_labels if row.token_id in holdout_ids)
        holdout_selected_ids = _select_token_ids(
            holdout_features, selection_feature, selection_operator, selection_threshold)
        holdout_baselines = baseline_families(
            holdout_labels, horizon=spec.candidate.horizon, feature_rows=holdout_features)
        holdout_candidate = score_candidate(
            spec.candidate.name, holdout_labels, horizon=spec.candidate.horizon,
            selected=lambda row: row.token_id in holdout_selected_ids,
            baseline_mean=holdout_baselines["no_trade"]["mean_return"],
            turnover=spec.costs.turnover, costs=spec.costs.scenarios,
            min_coverage=spec.candidate.min_coverage)
        holdout_selected_labels = tuple(
            label for label in holdout_labels if label.token_id in holdout_selected_ids
            and label.status == "COMPLETE" and label.value is not None)
        holdout_candidate, _ = _enrich_uncertainty(
            holdout_candidate, holdout_selected_labels, spec)
        holdout_evidence = _promotion_evidence(
            holdout_candidate, target_stage="holdout",
            discovery_adjusted_p_value=candidate_adjusted_p_value,
            validation_replicated=True, validation_semantics_frozen=True,
            holdout_adjusted_p_value=holdout_adjusted_p_value)
        decision = evaluate_candidate_promotion(
            holdout_candidate, holdout_evidence, spec.promotion_policy)
        stage_records.append({
            "stage": "holdout", "selection_threshold": selection_threshold,
            "selected_token_ids": sorted(holdout_selected_ids), "candidate": holdout_candidate,
            "promotion": decision,
        })
    stress_matrix = _build_stress_matrix(
        selected_token_ids=selected_ids, labels=discovery_labels,
        feature_rows=discovery_features, horizon=spec.candidate.horizon,
        turnover=spec.costs.turnover, policy=spec.stress)
    stability = build_stability_evidence(
        selected_token_ids=selected_ids, labels=discovery_labels, cohort=cohort,
        feature_rows=discovery_features, horizon=spec.candidate.horizon, policy=spec.stability)
    negative_controls = build_negative_control_evidence(
        selected_token_ids=selected_ids, labels=discovery_labels, horizon=spec.candidate.horizon,
        turnover=spec.costs.turnover, costs=spec.costs.scenarios,
        min_coverage=spec.candidate.min_coverage, policy=spec.negative_controls,
        score_candidate=score_candidate, baseline_families=baseline_families)
    falsification = build_falsification_evidence(
        policy=spec.falsification, negative_controls=negative_controls, stability=stability)

    spec_id = experiment_spec_id(spec)
    walk_forward_evidence = (_walk_forward_results(walk_forward, feature_rows, candidate_labels, spec)
                             if walk_forward is not None else None)
    validation_closure = build_validation_closure(
        spec_id=spec_id, selected_token_ids=selected_ids, promotion=asdict(decision),
        uncertainty=uncertainty, stress=stress_matrix, stability=stability,
        negative_controls=negative_controls, walk_forward=walk_forward_evidence)
    inputs = {"experiment_spec_id": spec_id, "dataset_identity": snapshot.dataset_identity,
              "code_version": spec.code_version, "manifest_version": MANIFEST_VERSION}
    if significance_bundle is not None:
        inputs["significance_evidence_id"] = hashlib.sha256(
            _dump(significance_bundle)).hexdigest()[:24]
    if confirmation_significance_evidence is not None:
        inputs["confirmation_significance_evidence_id"] = hashlib.sha256(
            _dump(confirmation_significance_evidence)).hexdigest()[:24]
    if spec.research_question_id is not None:
        inputs["research_question_id"] = spec.research_question_id
        inputs["research_hypothesis_id"] = spec.research_hypothesis_id
    run_id = hashlib.sha256(_dump(inputs)).hexdigest()[:24]
    target = Path(output_dir) / run_id
    target.mkdir(parents=True, exist_ok=True)

    definitions = {
        "features": {feature.name: {"version": feature.version, "definition_id": feature_definition_id(feature)}
                    for feature in registry.definitions()},
        "labels": {label.horizon: {"version": label.version, "definition_id": label_definition_id(label)}
                  for label in spec.labels},
    }

    artifacts = {
        "spec.json": experiment_spec_dict(spec),
        "cohort.json": cohort,
        "features.json": feature_rows,
        "labels.json": labels_by_horizon,
        "split.json": split.as_dict(),
        "baselines.json": baselines,
        "candidate.json": candidate,
        "promotion.json": decision,
        "promotion_stages.json": stage_records,
        "definitions.json": definitions,
        "hypothesis_family.json": hypothesis_family,
        "uncertainty.json": uncertainty,
        "stress_matrix.json": stress_matrix,
        "stability.json": stability,
        "negative_controls.json": negative_controls,
        "falsification.json": falsification,
        "validation_closure.json": validation_closure,
    }
    if significance_bundle is not None:
        artifacts["significance_evidence.json"] = significance_bundle
        artifacts["significance_evaluation.json"] = significance_evaluation
    if validation_candidate is not None:
        artifacts["validation_candidate.json"] = validation_candidate
    if holdout_candidate is not None:
        artifacts["holdout_candidate.json"] = holdout_candidate
    if confirmation_bundle is not None:
        artifacts["confirmation_significance_evidence.json"] = confirmation_bundle
        artifacts["confirmation_significance_evaluation.json"] = confirmation_evaluation
    if walk_forward is not None:
        artifacts["walk_forward.json"] = walk_forward_evidence
    manifest = {"manifest_version": MANIFEST_VERSION, "run_id": run_id, "immutable": True,
                "inputs": inputs, "artifacts": {name: hashlib.sha256(_dump(value)).hexdigest()
                                                for name, value in artifacts.items()}}
    for name, value in {**artifacts, "manifest.json": manifest}.items():
        path = target / name
        content = _dump(value)
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"immutable experiment run artifact differs: {path}")
        if not path.exists():
            path.write_bytes(content)
    return target
