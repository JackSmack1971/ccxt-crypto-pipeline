"""Slice 8R.7a: caller-supplied raw significance-evidence contract.

Selecting or computing a statistical test is explicitly out of scope here
(ROADMAP.md's Slice 8R.7a, Candidate A). This module only defines the
provenance-bound, immutable representation of one externally supplied raw
p-value per frozen hypothesis, and the fail-closed validation that binds a
complete set of that evidence to exactly one frozen hypothesis family, stage,
experiment spec, and dataset before it may be handed to
``evaluate_hypothesis_family`` (``hypotheses.py``) for multiple-testing
correction. Nothing here performs that correction, and nothing here is wired
into ``runner.py``/``campaign.py`` execution -- that integration is Slice
8R.7b, and ``PromotionEvidence.discovery_adjusted_p_value`` continues to be
withheld by the governed runner until then.

Externally supplied does not mean externally trusted: evidence for the wrong
hypothesis, family, stage, dataset, or experiment spec fails closed, as does
missing, extra, or duplicate/conflicting evidence. Nothing here supplies a
default p-value.

This evidence is observed *result* data, not pre-registered methodology, so
it deliberately does not join ``ExperimentSpec.spec_version`` (methodology
identity) or ``runner.py``'s ``MANIFEST_VERSION`` (run/result identity) --
see ROADMAP.md's Slice 8R.7a "Artifact and manifest identity" discussion.
This module versions its own evidence/bundle identity instead
(``SIGNIFICANCE_MANIFEST_VERSION``); wiring it into run identity is deferred
to 8R.7b, which actually consumes it.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .hypotheses import FrozenHypothesisFamily, HypothesisIdentity, verify_frozen_family_identity

SIGNIFICANCE_MANIFEST_VERSION = "phase8r-significance-evidence-v1"
SIGNIFICANCE_STAGES = ("discovery", "confirmation")


def _content_id(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:24]


def _parse_boundary(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid significance evidence temporal boundary: {value}") from exc


@dataclass(frozen=True)
class SignificanceEvidence:
    """One caller-supplied raw significance observation for a single frozen hypothesis.

    ``observed_through`` is the temporal boundary (evaluation/observation
    cutoff) the raw evidence was computed against, kept as its own field
    rather than folded into ``evidence_id`` implicitly so a widened or
    shifted boundary changes the content identity instead of silently
    reusing a prior one.
    """

    evidence_id: str
    hypothesis: HypothesisIdentity
    family_id: str
    experiment_spec_id: str
    dataset_version: str
    stage: str
    raw_p_value: float | None
    statistical_test: str
    test_version: str
    observed_through: str
    provenance: str
    parameters: tuple[tuple[str, Any], ...] = ()
    seed: int | None = None

    def __post_init__(self):
        if self.stage not in SIGNIFICANCE_STAGES:
            raise ValueError(f"unsupported significance-evidence stage: {self.stage}")
        if self.raw_p_value is not None and (
            isinstance(self.raw_p_value, bool) or not isinstance(self.raw_p_value, (int, float))
            or not math.isfinite(self.raw_p_value) or not 0 <= self.raw_p_value <= 1
        ):
            raise ValueError("significance evidence raw p-value must be finite in [0, 1] or explicit None")
        if not self.family_id.strip() or not self.experiment_spec_id.strip():
            raise ValueError("significance evidence requires a family and experiment spec identity")
        if not self.dataset_version.strip():
            raise ValueError("significance evidence requires a dataset version")
        if not self.statistical_test.strip() or not self.test_version.strip():
            raise ValueError("significance evidence requires a statistical test identity and version")
        if not self.provenance.strip():
            raise ValueError("significance evidence requires a provenance/source identity")
        _parse_boundary(self.observed_through)
        if self.seed is not None and (isinstance(self.seed, bool) or type(self.seed) is not int or self.seed < 0):
            raise ValueError("significance evidence seed must be a non-negative integer")


def _evidence_payload(*, hypothesis: HypothesisIdentity, family_id: str, experiment_spec_id: str,
                      dataset_version: str, stage: str, raw_p_value: float | None,
                      statistical_test: str, test_version: str, observed_through: str,
                      provenance: str, parameters: tuple[tuple[str, Any], ...],
                      seed: int | None) -> dict[str, Any]:
    return {
        "hypothesis": asdict(hypothesis), "family_id": family_id, "experiment_spec_id": experiment_spec_id,
        "dataset_version": dataset_version, "stage": stage, "raw_p_value": raw_p_value,
        "statistical_test": statistical_test, "test_version": test_version,
        "observed_through": observed_through, "provenance": provenance,
        "parameters": [list(item) for item in parameters], "seed": seed,
    }


def build_significance_evidence(
    hypothesis: HypothesisIdentity, *, family_id: str, experiment_spec_id: str, dataset_version: str,
    stage: str, raw_p_value: float | None, statistical_test: str, test_version: str,
    observed_through: str, provenance: str, parameters: Mapping[str, Any] | None = None,
    seed: int | None = None,
) -> SignificanceEvidence:
    """Construct one content-addressed significance-evidence entry.

    ``evidence_id`` is derived from the full payload, so changing any
    identity, provenance, or parameter field yields a distinct identity
    rather than silently reusing a prior one.
    """
    ordered_parameters = tuple(sorted((parameters or {}).items()))
    evidence_id = _content_id(_evidence_payload(
        hypothesis=hypothesis, family_id=family_id, experiment_spec_id=experiment_spec_id,
        dataset_version=dataset_version, stage=stage, raw_p_value=raw_p_value,
        statistical_test=statistical_test, test_version=test_version, observed_through=observed_through,
        provenance=provenance, parameters=ordered_parameters, seed=seed))
    return SignificanceEvidence(
        evidence_id=evidence_id, hypothesis=hypothesis, family_id=family_id,
        experiment_spec_id=experiment_spec_id, dataset_version=dataset_version, stage=stage,
        raw_p_value=raw_p_value, statistical_test=statistical_test, test_version=test_version,
        observed_through=observed_through, provenance=provenance, parameters=ordered_parameters, seed=seed,
    )


@dataclass(frozen=True)
class SignificanceEvidenceBundle:
    """A complete, validated significance-evidence set for exactly one frozen
    hypothesis family, stage, experiment spec, and dataset.

    Only :func:`build_significance_evidence_bundle` constructs a validated
    instance; ``entries`` is ordered to match ``family.hypotheses`` exactly.
    """

    manifest_version: str
    family_id: str
    experiment_spec_id: str
    dataset_version: str
    stage: str
    entries: tuple[SignificanceEvidence, ...]

    def raw_p_values(self) -> dict[str, float | None]:
        """The ``evaluate_hypothesis_family``-ready raw-p-value mapping, keyed
        by ``HypothesisIdentity.key`` -- the exact boundary Slice 8R.7b consumes.
        """
        return {entry.hypothesis.key: entry.raw_p_value for entry in self.entries}


def build_significance_evidence_bundle(
    family: FrozenHypothesisFamily, entries: Sequence[SignificanceEvidence], *,
    stage: str, dataset_version: str,
) -> SignificanceEvidenceBundle:
    """Validate caller-supplied significance evidence against a frozen hypothesis family.

    Fails closed on evidence bound to the wrong family, experiment spec,
    dataset, or stage; on evidence for a hypothesis outside the frozen
    family; on missing/incomplete family membership; and on duplicate or
    conflicting evidence for the same hypothesis. Performs no correction --
    the returned bundle's ``raw_p_values()`` is the input Slice 8R.7b feeds
    to ``evaluate_hypothesis_family``.
    """
    if stage not in SIGNIFICANCE_STAGES:
        raise ValueError(f"unsupported significance-evidence stage: {stage}")
    if not dataset_version.strip():
        raise ValueError("significance evidence requires a dataset version")
    verify_frozen_family_identity(family)

    expected = {item.key: item for item in family.hypotheses}
    seen: dict[str, SignificanceEvidence] = {}
    observed_through: str | None = None
    for entry in entries:
        if entry.family_id != family.family_id:
            raise ValueError(f"significance evidence bound to a different hypothesis family: {entry.evidence_id}")
        if entry.experiment_spec_id != family.experiment_spec_id:
            raise ValueError(f"significance evidence bound to a different experiment spec: {entry.evidence_id}")
        if entry.dataset_version != dataset_version:
            raise ValueError(f"significance evidence bound to a different dataset version: {entry.evidence_id}")
        if entry.stage != stage:
            raise ValueError(f"significance evidence bound to a different stage: {entry.evidence_id}")
        if observed_through is None:
            observed_through = entry.observed_through
        elif entry.observed_through != observed_through:
            raise ValueError("significance evidence must share one observed-through boundary")
        key = entry.hypothesis.key
        if key not in expected:
            raise ValueError(
                f"significance evidence references a hypothesis outside the frozen family: {entry.evidence_id}")
        if key in seen:
            raise ValueError(f"duplicate or conflicting significance evidence for hypothesis: {key}")
        seen[key] = entry

    missing = expected.keys() - seen.keys()
    if missing:
        raise ValueError(
            f"significance evidence is incomplete for frozen family {family.family_id}: missing={len(missing)}")

    return SignificanceEvidenceBundle(
        manifest_version=SIGNIFICANCE_MANIFEST_VERSION, family_id=family.family_id,
        experiment_spec_id=family.experiment_spec_id, dataset_version=dataset_version, stage=stage,
        entries=tuple(seen[item.key] for item in family.hypotheses),
    )
