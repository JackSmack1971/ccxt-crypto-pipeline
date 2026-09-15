"""Frozen, content-addressed hypothesis-family evaluation contracts."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import asdict, dataclass
from typing import Mapping

from analysis.alpha import Hypothesis, apply_bh_fdr, apply_holm

from .spec import ExperimentSpec, experiment_spec_id

FAMILY_MANIFEST_VERSION = "phase6-hypothesis-family-v1"


@dataclass(frozen=True, order=True)
class HypothesisIdentity:
    feature: str
    threshold: str
    horizon: str
    subgroup: str | None
    model_specification: str

    @property
    def key(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class FrozenHypothesisFamily:
    """The exact family committed before any result is evaluated."""

    manifest_version: str
    family_id: str
    experiment_spec_id: str
    name: str
    discovery_correction: str
    discovery_q: float
    confirmation_correction: str
    confirmation_alpha: float
    hypotheses: tuple[HypothesisIdentity, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FamilyEvaluation:
    family_id: str
    stage: str
    correction: str
    threshold: float
    hypotheses: tuple[Hypothesis, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _content_id(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:24]


def _family_payload(family: FrozenHypothesisFamily) -> dict[str, object]:
    return {
        "manifest_version": family.manifest_version,
        "experiment_spec_id": family.experiment_spec_id,
        "name": family.name,
        "discovery_correction": family.discovery_correction,
        "discovery_q": family.discovery_q,
        "confirmation_correction": family.confirmation_correction,
        "confirmation_alpha": family.confirmation_alpha,
        "hypotheses": [asdict(item) for item in family.hypotheses],
    }


def freeze_hypothesis_family(spec: ExperimentSpec) -> FrozenHypothesisFamily:
    """Expand and content-identify the complete declared Cartesian grid."""
    family = spec.hypothesis_family
    hypotheses = tuple(
        HypothesisIdentity(*parts, family.model_specification)
        for parts in itertools.product(
            sorted(family.features), sorted(family.thresholds), sorted(family.horizons),
            sorted(family.subgroups, key=lambda value: value or ""),
        )
    )
    payload = {
        "manifest_version": FAMILY_MANIFEST_VERSION,
        "experiment_spec_id": experiment_spec_id(spec),
        "name": family.name,
        "discovery_correction": family.discovery_correction,
        "discovery_q": family.discovery_q,
        "confirmation_correction": family.confirmation_correction,
        "confirmation_alpha": family.confirmation_alpha,
        "hypotheses": [asdict(item) for item in hypotheses],
    }
    return FrozenHypothesisFamily(
        family_id=_content_id(payload), hypotheses=hypotheses,
        **{key: value for key, value in payload.items() if key != "hypotheses"},
    )


def evaluate_hypothesis_family(
    family: FrozenHypothesisFamily,
    raw_p_values: Mapping[str, float | None],
    *,
    stage: str,
    dataset_version: str,
    date_tested: str,
) -> FamilyEvaluation:
    """Correct a complete result set without permitting family redefinition."""
    if family.manifest_version != FAMILY_MANIFEST_VERSION or _content_id(_family_payload(family)) != family.family_id:
        raise ValueError("hypothesis family content does not match its frozen identity")
    if stage not in {"discovery", "confirmation"}:
        raise ValueError("hypothesis-family stage must be discovery or confirmation")
    if not dataset_version.strip() or not date_tested.strip():
        raise ValueError("hypothesis-family evaluation requires dataset version and date tested")
    expected = {item.key for item in family.hypotheses}
    supplied = set(raw_p_values)
    if supplied != expected:
        raise ValueError(
            f"hypothesis results do not match frozen family {family.family_id}: "
            f"missing={len(expected - supplied)}, extra={len(supplied - expected)}"
        )
    for value in raw_p_values.values():
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 1
        ):
            raise ValueError("raw p-values must be finite values in [0, 1] or explicit None")

    hypotheses = [Hypothesis(
        family.experiment_spec_id, item.feature, (), item.threshold, item.horizon,
        item.subgroup, item.model_specification, date_tested, dataset_version,
        raw_p_values[item.key],
    ) for item in family.hypotheses]
    if stage == "discovery":
        correction, threshold = family.discovery_correction, family.discovery_q
        corrected = apply_bh_fdr(hypotheses, threshold)
    else:
        correction, threshold = family.confirmation_correction, family.confirmation_alpha
        corrected = apply_holm(hypotheses, threshold)
    return FamilyEvaluation(family.family_id, stage, correction, threshold, corrected)
