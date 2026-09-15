from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Callable

@dataclass(frozen=True)
class SplitResult:
    discovery: tuple[str, ...]; validation: tuple[str, ...]; holdout: tuple[str, ...]
    boundaries: tuple[dict[str, str], ...] = ()
    removed: tuple[dict[str, str], ...] = ()
    embargo_days: int = 7
    feature_lookback_seconds: int = 0
    label_horizon_seconds: int = 7 * 24 * 60 * 60
    sealed: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"discovery": list(self.discovery), "validation": list(self.validation),
                "holdout": list(self.holdout), "boundaries": list(self.boundaries),
                "removed": list(self.removed), "embargo_days": self.embargo_days,
                "feature_lookback_seconds": self.feature_lookback_seconds,
                "label_horizon_seconds": self.label_horizon_seconds,
                "sealed": self.sealed}

def build_split(cohort: tuple[Any, ...], *, embargo_days: int = 7,
                feature_lookback: timedelta = timedelta(0),
                label_horizon: timedelta = timedelta(days=7)) -> SplitResult:
    """Build a chronological split and remove rows that leak across boundaries.

    The initial 60/20/20 assignment fixes both boundaries and sealed holdout
    membership.  A row on the earlier side is purged when its label window
    reaches the next boundary.  A row on the later side is purged when its
    feature lookback reaches before that boundary, and is embargoed when its
    decision time is inside the configured post-boundary interval.
    """
    if embargo_days < 0:
        raise ValueError("embargo_days must be non-negative")
    if feature_lookback < timedelta(0) or label_horizon < timedelta(0):
        raise ValueError("feature lookback and label horizon must be non-negative")
    ordered = sorted(cohort, key=lambda x: (x.t0, x.token_id)); n = len(ordered)
    a, b = int(n * .6), int(n * .8)
    groups = [ordered[:a], ordered[a:b], ordered[b:]]
    boundary_rows = (("discovery_validation", ordered[a]) if a < n else None,
                     ("validation_holdout", ordered[b]) if b < n else None)
    boundaries = tuple({"name": name, "timestamp": row.t0.isoformat(), "first_later_token_id": row.token_id}
                       for item in boundary_rows if item is not None for name, row in (item,))
    removed: list[dict[str, str]] = []
    embargo = timedelta(days=embargo_days)

    def reject(row: Any, partition: str, boundary_name: str, boundary: datetime,
               *, earlier: bool) -> bool:
        reason = None
        if earlier and row.t0 + label_horizon >= boundary:
            reason = "LABEL_WINDOW_OVERLAP"
        elif not earlier and row.t0 - feature_lookback < boundary:
            reason = "FEATURE_WINDOW_OVERLAP"
        elif not earlier and embargo and row.t0 < boundary + embargo:
            reason = "EMBARGO"
        if reason:
            removed.append({"token_id": row.token_id, "partition": partition, "reason": reason,
                            "boundary": boundary_name, "boundary_timestamp": boundary.isoformat()})
        return reason is not None

    names = ("discovery", "validation", "holdout")
    kept: list[list[Any]] = [list(group) for group in groups]
    if a < n:
        boundary = ordered[a].t0
        kept[0] = [row for row in kept[0] if not reject(row, names[0], "discovery_validation", boundary, earlier=True)]
        kept[1] = [row for row in kept[1] if not reject(row, names[1], "discovery_validation", boundary, earlier=False)]
    if b < n:
        boundary = ordered[b].t0
        kept[1] = [row for row in kept[1] if not reject(row, names[1], "validation_holdout", boundary, earlier=True)]
        kept[2] = [row for row in kept[2] if not reject(row, names[2], "validation_holdout", boundary, earlier=False)]
    return SplitResult(*(tuple(row.token_id for row in group) for group in kept), boundaries,
                       tuple(removed), embargo_days, int(feature_lookback.total_seconds()),
                       int(label_horizon.total_seconds()))

@dataclass(frozen=True)
class Hypothesis:
    experiment_id: str; feature: str; transformations: tuple[str, ...]; threshold: str | None
    horizon: str; subgroup: str | None; model_specification: str; date_tested: str; dataset_version: str
    raw_p_value: float | None; adjusted_value: float | None = None; decision: str = "rejected"

class HypothesisRegistry:
    def __init__(self):
        self.items: list[Hypothesis] = []
        self.promotions: list[dict[str, Any]] = []
    def add(self, hypothesis: Hypothesis): self.items.append(hypothesis)
    def as_dicts(self): return [asdict(x) for x in self.items]
    def count(self): return len(self.items)

    def record_promotion(self, candidate: CandidateResult, inputs: PromotionEvidence,
                         decision: PromotionDecision) -> None:
        """Retain the exact governed inputs and decision beside hypotheses."""
        candidate_inputs = {key: value for key, value in asdict(candidate).items() if key != "promotion"}
        self.promotions.append({"candidate": candidate.name, "candidate_inputs": candidate_inputs,
                                "inputs": asdict(inputs),
                                "decision": asdict(decision)})

    def as_artifact(self) -> dict[str, Any]:
        return {"hypotheses": self.as_dicts(), "promotions": list(self.promotions)}

def apply_bh_fdr(hypotheses: list[Hypothesis], q: float = .05) -> tuple[Hypothesis, ...]:
    indexed = sorted(((h.raw_p_value, i) for i, h in enumerate(hypotheses) if h.raw_p_value is not None), key=lambda x: x[0])
    adjusted = [None] * len(hypotheses); running = 1.0; m = len(indexed)
    for rank, (p, index) in reversed(list(enumerate(indexed, 1))):
        running = min(running, p * m / rank); adjusted[index] = running
    return tuple(Hypothesis(**{**asdict(h), "adjusted_value": adjusted[i], "decision": "promoted" if adjusted[i] is not None and adjusted[i] <= q else "rejected"}) for i, h in enumerate(hypotheses))

def apply_holm(hypotheses: list[Hypothesis], alpha: float = .05) -> tuple[Hypothesis, ...]:
    indexed = sorted(((h.raw_p_value, i) for i, h in enumerate(hypotheses) if h.raw_p_value is not None), key=lambda x: x[0]); m = len(indexed)
    adjusted = [None] * len(hypotheses)
    running = 0.0
    for rank, (p, index) in enumerate(indexed):
        running = max(running, min(1.0, p * (m - rank)))
        adjusted[index] = running
    return tuple(Hypothesis(**{**asdict(h), "adjusted_value": adjusted[i], "decision": "confirmed" if adjusted[i] is not None and adjusted[i] <= alpha else "rejected"}) for i, h in enumerate(hypotheses))

@dataclass(frozen=True)
class PromotionPolicy:
    """Versioned mandatory gates for candidate research-state promotion."""

    version: str = "candidate-promotion-v1"
    minimum_sample_size: int = 10
    minimum_independent_launches: int = 10
    minimum_coverage: float = .8
    minimum_effect_size: float = .01
    discovery_correction: str = "benjamini-hochberg"
    discovery_q: float = .05
    confirmation_correction: str = "holm-bonferroni"
    confirmation_alpha: float = .05

    def __post_init__(self):
        if type(self.minimum_sample_size) is not int or self.minimum_sample_size < 1:
            raise ValueError("minimum sample size must be a positive integer")
        if type(self.minimum_independent_launches) is not int or self.minimum_independent_launches < 1:
            raise ValueError("minimum independent launches must be a positive integer")
        if not (0 < self.minimum_coverage <= 1):
            raise ValueError("minimum coverage must be in (0, 1]")
        if not isinstance(self.minimum_effect_size, (int, float)) or not math.isfinite(self.minimum_effect_size) \
                or self.minimum_effect_size <= 0:
            raise ValueError("minimum effect size must be a positive finite number")


@dataclass(frozen=True)
class PromotionEvidence:
    """Frozen evidence submitted to a promotion stage; ``None`` means absent."""

    target_stage: str = "discovery"
    discovery_adjusted_p_value: float | None = None
    effect_size: float | None = None
    validation_replicated: bool | None = None
    validation_semantics_frozen: bool | None = None
    holdout_adjusted_p_value: float | None = None
    baseline_superior: bool | None = None
    uncertainty_supports_effect: bool | None = None
    cost_sensitivity_passed: bool | None = None


@dataclass(frozen=True)
class PromotionDecision:
    state: str
    reasons: tuple[str, ...]
    policy: dict[str, Any]
    inputs: dict[str, Any]


@dataclass(frozen=True)
class CandidateResult:
    name: str; horizon: str; sample_size: int; independent_launches: int; coverage: float; missingness: float
    mean_return: float | None; uncertainty: dict[str, float | None]; baseline_comparison: dict[str, Any]
    cost_sensitivity: dict[str, float | None]
    promotion: PromotionDecision

    @property
    def validated_alpha(self) -> bool:
        """Compatibility view: only sealed-holdout confirmation is validated."""
        return self.promotion.state == "holdout_confirmed"

    @property
    def status(self) -> str:
        return self.promotion.state


def _promotion_decision(state: str, reasons: list[str], policy: PromotionPolicy,
                        evidence: PromotionEvidence) -> PromotionDecision:
    return PromotionDecision(state, tuple(reasons), asdict(policy), asdict(evidence))


def evaluate_candidate_promotion(candidate: CandidateResult, evidence: PromotionEvidence,
                                 policy: PromotionPolicy = PromotionPolicy()) -> PromotionDecision:
    """Evaluate sequential research gates without inferring missing evidence.

    Discovery correction, baseline superiority, uncertainty/effect evidence, and
    configured cost sensitivity are mandatory before the first promotion.
    Validation then requires replication under frozen semantics, and final
    confirmation requires corrected testing of the sealed holdout.
    """
    if evidence.target_stage not in {"discovery", "validation", "holdout"}:
        raise ValueError("target_stage must be discovery, validation, or holdout")
    if candidate.sample_size < policy.minimum_sample_size:
        return _promotion_decision("insufficient_coverage", ["MINIMUM_SAMPLE_SIZE"], policy, evidence)
    if candidate.independent_launches < policy.minimum_independent_launches:
        return _promotion_decision("insufficient_coverage", ["MINIMUM_INDEPENDENT_LAUNCHES"], policy, evidence)
    if candidate.coverage < policy.minimum_coverage:
        return _promotion_decision("insufficient_coverage", ["MINIMUM_COVERAGE"], policy, evidence)

    valid_effect_size = (evidence.effect_size if isinstance(evidence.effect_size, (int, float))
                         and math.isfinite(evidence.effect_size) else None)
    required = {
        "MISSING_DISCOVERY_CORRECTION": evidence.discovery_adjusted_p_value,
        "MISSING_EFFECT_SIZE": valid_effect_size,
        "MISSING_BASELINE_COMPARISON": evidence.baseline_superior,
        "MISSING_UNCERTAINTY_EFFECT_EVIDENCE": evidence.uncertainty_supports_effect,
        "MISSING_COST_SENSITIVITY": evidence.cost_sensitivity_passed,
    }
    missing = [reason for reason, value in required.items() if value is None]
    if missing:
        return _promotion_decision("insufficient_evidence", missing, policy, evidence)
    failed = []
    if evidence.discovery_adjusted_p_value > policy.discovery_q:
        failed.append("DISCOVERY_CORRECTION_FAILED")
    if valid_effect_size < policy.minimum_effect_size:
        failed.append("PRACTICAL_EFFECT_TOO_SMALL")
    if not evidence.baseline_superior: failed.append("BASELINE_COMPARISON_FAILED")
    if not evidence.uncertainty_supports_effect: failed.append("UNCERTAINTY_EFFECT_FAILED")
    if not evidence.cost_sensitivity_passed: failed.append("COST_SENSITIVITY_FAILED")
    if candidate.baseline_comparison.get("difference") is None or candidate.baseline_comparison["difference"] <= 0:
        failed.append("BASELINE_EVIDENCE_NOT_POSITIVE")
    if candidate.uncertainty.get("ci95_low") is None or candidate.uncertainty["ci95_low"] <= 0:
        failed.append("UNCERTAINTY_EVIDENCE_NOT_POSITIVE")
    if not candidate.cost_sensitivity or any(value is None or value <= 0
                                             for value in candidate.cost_sensitivity.values()):
        failed.append("COST_EVIDENCE_NOT_ROBUST")
    if failed: return _promotion_decision("rejected", failed, policy, evidence)
    if evidence.target_stage == "discovery":
        return _promotion_decision("discovery_promoted", [], policy, evidence)

    validation = {"MISSING_VALIDATION_REPLICATION": evidence.validation_replicated,
                  "MISSING_FROZEN_VALIDATION_SEMANTICS": evidence.validation_semantics_frozen}
    missing = [reason for reason, value in validation.items() if value is None]
    if missing: return _promotion_decision("insufficient_evidence", missing, policy, evidence)
    failed = [reason for reason, value in (("VALIDATION_REPLICATION_FAILED", evidence.validation_replicated),
                                           ("VALIDATION_SEMANTICS_NOT_FROZEN", evidence.validation_semantics_frozen))
              if not value]
    if failed: return _promotion_decision("rejected", failed, policy, evidence)
    if evidence.target_stage == "validation":
        return _promotion_decision("validation_confirmed", [], policy, evidence)

    if evidence.holdout_adjusted_p_value is None:
        return _promotion_decision("insufficient_evidence", ["MISSING_HOLDOUT_CORRECTION"], policy, evidence)
    if evidence.holdout_adjusted_p_value > policy.confirmation_alpha:
        return _promotion_decision("rejected", ["HOLDOUT_CORRECTION_FAILED"], policy, evidence)
    return _promotion_decision("holdout_confirmed", [], policy, evidence)

def descriptive_baseline(labels: tuple[Any, ...], *, horizon: str) -> dict[str, Any]:
    """Compute the unconditional Stage A baseline without selecting winners."""
    rows = [x for x in labels if x.horizon == horizon]
    complete = [x for x in rows if x.status == "COMPLETE" and x.value is not None]
    values = sorted(float(x.value) for x in complete)
    median = values[len(values) // 2] if values else None
    if values and len(values) % 2 == 0: median = (values[len(values)//2 - 1] + values[len(values)//2]) / 2
    return {"horizon": horizon, "sample_count": len(complete), "coverage": len(complete) / len(rows) if rows else 0.0,
            "mean_return": sum(values) / len(values) if values else None, "median_return": median,
            "failure_rate": sum(x.status == "ECONOMIC_FAILURE" for x in rows) / len(rows) if rows else 0.0,
            "chain_breakdown": {chain: sum(1 for x in complete if x.token_id.startswith(chain + ":"))
                                for chain in sorted({x.token_id.split(":", 1)[0] for x in complete})},
            "censoring": {status: sum(x.status == status for x in rows) for status in
                          ("ECONOMIC_FAILURE", "DATA_CENSORED", "RIGHT_CENSORED")}}


def baseline_comparison(labels: tuple[Any, ...], *, horizon: str,
                        candidate_mean: float | None = None, feature_rows: tuple[dict[str, Any], ...] = ()) -> dict[str, Any]:
    """Return the mandatory descriptive no-trade reference comparison."""
    baseline = descriptive_baseline(labels, horizon=horizon)
    baseline["candidate_mean"] = candidate_mean
    baseline["candidate_minus_baseline"] = (
        candidate_mean - baseline["mean_return"]
        if candidate_mean is not None and baseline["mean_return"] is not None else None
    )
    baseline["baseline_family"] = "no_trade_unconditional"
    baseline["families"] = baseline_families(labels, horizon=horizon, feature_rows=feature_rows)
    return baseline


def baseline_families(labels: tuple[Any, ...], *, horizon: str,
                      feature_rows: tuple[dict[str, Any], ...] = ()) -> dict[str, Any]:
    """Compute supported descriptive references and preserve unavailable ones."""
    rows = [row for row in labels if row.horizon == horizon and row.status == "COMPLETE" and row.value is not None]
    by_id = {row.get("token_id"): row for row in feature_rows}

    def group(name: str, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        selected = [row for row in rows if predicate(by_id.get(row.token_id, {}))]
        return {"family": name, "status": "available" if selected else "unavailable",
                "sample_count": len(selected),
                "mean_return": sum(float(row.value) for row in selected) / len(selected) if selected else None}

    chains = {}
    for chain in sorted({row.token_id.split(":", 1)[0] for row in rows}):
        chains[chain] = group(f"market_chain:{chain}", lambda _features, c=chain: True)
        chain_rows = [row for row in rows if row.token_id.startswith(chain + ":")]
        chains[chain]["sample_count"] = len(chain_rows)
        chains[chain]["mean_return"] = (sum(float(row.value) for row in chain_rows) / len(chain_rows)
                                         if chain_rows else None)
    result = {"no_trade": descriptive_baseline(labels, horizon=horizon), "market_chain": chains}
    result["age_liquidity"] = group("age_liquidity", lambda features: "age_hours" in features or "launch_liquidity_usd" in features)
    result["momentum"] = group("momentum", lambda features: "lookback_return" in features)
    return result

def score_candidate(name: str, labels: tuple[Any, ...], *, horizon: str, selected: Callable[[Any], bool] | None = None,
                    baseline_mean: float | None = None, turnover: float = 0.0, costs: tuple[float, ...] = (0.0, .001, .005),
                    min_coverage: float = .8) -> CandidateResult:
    target = [x for x in labels if x.horizon == horizon]; complete = [x for x in target if x.status == "COMPLETE" and x.value is not None]
    chosen = [x for x in complete if selected is None or selected(x)]
    vals = [x.value for x in chosen]; n = len(target); mean = sum(vals) / len(vals) if vals else None
    variance = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1) if len(vals) > 1 else None
    se = math.sqrt(variance / len(vals)) if variance is not None else None
    coverage = len(chosen) / n if n else 0.0
    return CandidateResult(name, horizon, len(chosen), len({x.token_id for x in chosen}), coverage,
                           1.0 - coverage, mean, {"standard_error": se, "ci95_low": mean - 1.96 * se if mean is not None and se is not None else None,
                           "ci95_high": mean + 1.96 * se if mean is not None and se is not None else None},
                           {"baseline_mean": baseline_mean, "difference": mean - baseline_mean if mean is not None and baseline_mean is not None else None},
                           {str(c): (mean - turnover * c) if mean is not None else None for c in costs},
                           PromotionDecision("discovered", (), asdict(PromotionPolicy(minimum_coverage=min_coverage)),
                                             asdict(PromotionEvidence())))

def validate_temporal_alignment(cohort: tuple[Any, ...], feature_rows: tuple[dict[str, Any], ...],
                                labels: tuple[Any, ...]) -> None:
    """Reject rows whose identity/timestamps make leakage or permutation possible."""
    times = {x.token_id: x.t0.isoformat() for x in cohort}
    if len({x.token_id for x in cohort}) != len(cohort):
        raise ValueError("duplicate cohort identity")
    if len({x.get("token_id") for x in feature_rows}) != len(feature_rows):
        raise ValueError("duplicate feature identity")
    if len({(x.token_id, x.horizon) for x in labels}) != len(labels):
        raise ValueError("duplicate label identity")
    for row in feature_rows:
        if row.get("token_id") not in times or row.get("decision_time") != times[row["token_id"]]:
            raise ValueError("feature row is not aligned to the cohort decision time")
        for item in row.get("feature_provenance", {}).values():
            effective = item.get("effective_timestamp")
            latest = item.get("latest_allowed_timestamp", row["decision_time"])
            if effective != row["decision_time"] or effective > latest:
                raise ValueError("future feature observation")
    for label in labels:
        if label.token_id not in times or label.start_time != times[label.token_id]:
            raise ValueError("label row is permuted or future-aligned")

def rank_candidates(candidates: tuple[CandidateResult, ...] | list[CandidateResult]) -> tuple[CandidateResult, ...]:
    """Stable ranking by governed research state, then descriptive return."""
    priority = {"holdout_confirmed": 3, "validation_confirmed": 2, "discovery_promoted": 1}
    return tuple(sorted(candidates, key=lambda x: (-priority.get(x.promotion.state, 0),
        -(x.mean_return if x.mean_return is not None else float("-inf")), x.name, x.horizon)))
