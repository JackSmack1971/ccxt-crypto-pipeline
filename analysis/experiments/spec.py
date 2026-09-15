from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from analysis.alpha import CohortConfig, LabelDefinition, PromotionPolicy
from analysis.alpha.labels import HORIZONS as LABEL_HORIZONS
from analysis.alpha.registry import feature_policy_versions

SPEC_VERSION = "phase6-experiment-v1"
SUPPORTED_DISCOVERY_CORRECTIONS = ("benjamini-hochberg",)
SUPPORTED_CONFIRMATION_CORRECTIONS = ("holm-bonferroni",)
SUPPORTED_BASELINE_FAMILIES = ("no_trade", "market_chain", "age_liquidity", "momentum")


@dataclass(frozen=True)
class SplitPolicy:
    """Versioned chronological discovery/validation/holdout split configuration."""

    version: str = "phase6-split-v1"
    embargo_days: int = 7
    feature_lookback_seconds: int = 0
    label_horizon_seconds: int = 7 * 24 * 60 * 60

    def __post_init__(self):
        if not self.version.strip():
            raise ValueError("split policy requires a version")
        if self.embargo_days < 0:
            raise ValueError("embargo_days must be non-negative")
        if self.feature_lookback_seconds < 0 or self.label_horizon_seconds < 0:
            raise ValueError("split windows must be non-negative")


@dataclass(frozen=True)
class HypothesisFamily:
    """A frozen multiplicity family: every feature/threshold/horizon/subgroup
    combination that will be tested together under one correction policy.

    Freezing this family before evaluation and preventing post-result
    redefinition is Slice 6.4's contract; this object only versions the
    declared grid and its correction identity.
    """

    name: str
    features: tuple[str, ...]
    thresholds: tuple[str, ...]
    horizons: tuple[str, ...]
    subgroups: tuple[str | None, ...] = (None,)
    model_specification: str = "descriptive_mean_return"
    discovery_correction: str = "benjamini-hochberg"
    discovery_q: float = 0.05
    confirmation_correction: str = "holm-bonferroni"
    confirmation_alpha: float = 0.05

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("hypothesis family requires a name")
        if not self.features or any(not item.strip() for item in self.features):
            raise ValueError("hypothesis family requires at least one non-blank feature")
        if not self.thresholds or any(not item.strip() for item in self.thresholds):
            raise ValueError("hypothesis family requires at least one non-blank threshold")
        if not self.horizons or any(not item.strip() for item in self.horizons):
            raise ValueError("hypothesis family requires at least one non-blank horizon")
        if not self.subgroups:
            raise ValueError("hypothesis family requires at least one subgroup declaration")
        if len(set(self.features)) != len(self.features):
            raise ValueError("hypothesis family features must be unique")
        if len(set(self.thresholds)) != len(self.thresholds):
            raise ValueError("hypothesis family thresholds must be unique")
        if len(set(self.horizons)) != len(self.horizons):
            raise ValueError("hypothesis family horizons must be unique")
        if len(set(self.subgroups)) != len(self.subgroups):
            raise ValueError("hypothesis family subgroups must be unique")
        if self.discovery_correction not in SUPPORTED_DISCOVERY_CORRECTIONS:
            raise ValueError(f"unsupported discovery correction: {self.discovery_correction}")
        if self.confirmation_correction not in SUPPORTED_CONFIRMATION_CORRECTIONS:
            raise ValueError(f"unsupported confirmation correction: {self.confirmation_correction}")
        if not (0 < self.discovery_q <= 1) or not (0 < self.confirmation_alpha <= 1):
            raise ValueError("correction thresholds must be in (0, 1]")

    @property
    def size(self) -> int:
        """Total hypothesis count implied by the declared grid."""
        return len(self.features) * len(self.thresholds) * len(self.horizons) * len(self.subgroups)


@dataclass(frozen=True)
class CandidateDefinition:
    """A declarative candidate-selection identity.

    The spec stores a selection-rule identity string rather than an
    executable callable so the object remains hashable, serializable, and
    free of hidden behavior; a runner resolves the rule to code.
    """

    name: str
    horizon: str
    selection_rule: str
    min_coverage: float = 0.8

    def __post_init__(self):
        if not self.name.strip() or not self.selection_rule.strip():
            raise ValueError("candidate definition requires a name and selection rule")
        if not (0 < self.min_coverage <= 1):
            raise ValueError("candidate minimum coverage must be in (0, 1]")


@dataclass(frozen=True)
class CostPolicy:
    """Versioned turnover/cost-sensitivity scenarios for candidate scoring."""

    version: str = "phase6-cost-v1"
    turnover: float = 0.0
    scenarios: tuple[float, ...] = (0.0, 0.001, 0.005)

    def __post_init__(self):
        if not self.version.strip():
            raise ValueError("cost policy requires a version")
        if self.turnover < 0:
            raise ValueError("turnover must be non-negative")
        if not self.scenarios:
            raise ValueError("cost policy requires at least one scenario")
        if any(value < 0 for value in self.scenarios):
            raise ValueError("cost scenarios must be non-negative")
        if len(set(self.scenarios)) != len(self.scenarios):
            raise ValueError("cost scenarios must be unique")


@dataclass(frozen=True)
class BaselinePolicy:
    """Declares which mandatory baseline families this experiment requires."""

    families: tuple[str, ...] = SUPPORTED_BASELINE_FAMILIES

    def __post_init__(self):
        if "no_trade" not in self.families:
            raise ValueError("baseline policy must include the mandatory no_trade family")
        unsupported = sorted(set(self.families) - set(SUPPORTED_BASELINE_FAMILIES))
        if unsupported:
            raise ValueError(f"unsupported baseline family: {', '.join(unsupported)}")
        if len(set(self.families)) != len(self.families):
            raise ValueError("baseline families must be unique")


@dataclass(frozen=True)
class ExperimentSpec:
    """A versioned, declarative composition of the governed Phase 2-3
    configuration objects that together define one reproducible research
    experiment.

    This spec never executes cohort extraction, feature computation,
    labeling, splitting, or candidate evaluation itself. It only versions,
    cross-validates, and content-identifies the configuration those
    already-governed Phase 3 helpers require, so a later slice can execute it
    without redefining research semantics or creating a second engine.
    """

    spec_version: str
    name: str
    cohort: CohortConfig
    feature_set: tuple[str, ...]
    feature_policy_version: str
    labels: tuple[LabelDefinition, ...]
    split: SplitPolicy
    hypothesis_family: HypothesisFamily
    candidate: CandidateDefinition
    costs: CostPolicy
    baselines: BaselinePolicy
    promotion_policy: PromotionPolicy
    code_version: str
    config_identity: str

    def __post_init__(self):
        if self.spec_version != SPEC_VERSION:
            raise ValueError(f"unsupported experiment spec version: {self.spec_version}")
        if not self.name.strip():
            raise ValueError("experiment spec requires a name")
        if not self.feature_set or any(not item.strip() for item in self.feature_set):
            raise ValueError("experiment spec requires at least one non-blank feature")
        if len(set(self.feature_set)) != len(self.feature_set):
            raise ValueError("feature_set entries must be unique")
        object.__setattr__(self, "feature_set", tuple(sorted(self.feature_set)))
        if not self.feature_policy_version.strip():
            raise ValueError("experiment spec requires a feature policy version")
        catalog_versions = feature_policy_versions(self.feature_policy_version)
        unresolved_features = sorted(set(self.feature_set) - set(catalog_versions))
        if unresolved_features:
            raise ValueError(f"unsupported experiment feature identity: {', '.join(unresolved_features)}")
        if not self.labels:
            raise ValueError("experiment spec requires at least one label definition")
        label_horizons = tuple(label.horizon for label in self.labels)
        if len(set(label_horizons)) != len(label_horizons):
            raise ValueError("experiment spec labels must declare unique horizons")

        unresolved = sorted(set(self.hypothesis_family.horizons) - set(label_horizons))
        if unresolved:
            raise ValueError(f"hypothesis family references undeclared label horizons: {', '.join(unresolved)}")
        if self.candidate.horizon not in label_horizons:
            raise ValueError(f"candidate definition references an undeclared label horizon: {self.candidate.horizon}")
        if self.candidate.horizon not in self.hypothesis_family.horizons:
            raise ValueError("candidate definition horizon must be tested by the hypothesis family")

        longest_label_seconds = max(int(LABEL_HORIZONS[horizon][0].total_seconds()) for horizon in label_horizons)
        if self.split.label_horizon_seconds < longest_label_seconds:
            raise ValueError("split label-horizon window is shorter than the longest declared label horizon")

        if self.promotion_policy.discovery_correction != self.hypothesis_family.discovery_correction:
            raise ValueError("promotion policy discovery correction must match the hypothesis family")
        if self.promotion_policy.confirmation_correction != self.hypothesis_family.confirmation_correction:
            raise ValueError("promotion policy confirmation correction must match the hypothesis family")
        if self.promotion_policy.discovery_q != self.hypothesis_family.discovery_q:
            raise ValueError("promotion policy discovery threshold must match the hypothesis family")
        if self.promotion_policy.confirmation_alpha != self.hypothesis_family.confirmation_alpha:
            raise ValueError("promotion policy confirmation threshold must match the hypothesis family")

        if not self.code_version.strip() or not self.config_identity.strip():
            raise ValueError("experiment spec requires code and config identities")


def _dump(value: Any) -> bytes:
    return (json.dumps(value, default=str, sort_keys=True, separators=(",", ":")) + "\n").encode()


def experiment_spec_dict(spec: ExperimentSpec) -> dict[str, Any]:
    """Return a canonical, JSON-safe representation of the spec."""
    return asdict(spec)


def experiment_spec_id(spec: ExperimentSpec) -> str:
    """Deterministic content-addressed identity; identical specs hash identically."""
    return hashlib.sha256(_dump(experiment_spec_dict(spec))).hexdigest()[:24]
