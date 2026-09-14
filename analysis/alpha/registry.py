"""Durable identities, semantic versions, and compatibility rules for the
Phase 3 feature/label constructors.

This module computes no feature or label values itself. It only names,
versions, and cross-references the already-governed constructors in
``features.py``/``labels.py`` so a Phase 6 experiment can reference a
feature by a durable (name, version) identity instead of an unversioned
bare name, a run manifest can prove exactly which versioned definition
produced its values (see ``feature_definition_id``/``label_definition_id``),
and a later run comparison can be rejected as methodologically incompatible
rather than silently assumed comparable.
"""

from __future__ import annotations

from typing import Callable

from .features import FeatureDefinition, close_return_feature, launch_liquidity_feature
from .labels import HORIZONS

FeatureFactory = Callable[..., FeatureDefinition]

# Every implemented (name, version) pair a Phase 6 experiment may reference,
# mapped to the constructor that produces its canonical FeatureDefinition.
# Adding a new version here — never mutating an existing entry's behavior in
# place — is the only supported way to change what a feature computes.
_FEATURE_CATALOG: dict[tuple[str, str], FeatureFactory] = {
    ("launch_liquidity_usd", "v1"): lambda **_: launch_liquidity_feature(),
    ("lookback_return", "v1"): lambda *, lookback, **_: close_return_feature(lookback),
}

# Declares which versions of the same named feature are safe to compare or
# substitute for one another (e.g. a documented non-breaking clarification).
# Empty by default: an undeclared cross-version comparison fails closed
# rather than assuming compatibility. No entry needs a non-empty tuple yet
# because only one version of each feature is implemented; later versions
# populate this explicitly rather than by inference.
FEATURE_COMPATIBILITY: dict[tuple[str, str], tuple[str, ...]] = {key: () for key in _FEATURE_CATALOG}

# Named, frozen bundles of per-feature versions an ExperimentSpec references
# by one pointer (`feature_policy_version`) instead of repeating a version
# per declared feature.
FEATURE_POLICIES: dict[str, dict[str, str]] = {
    "phase3-feature-v1": {"launch_liquidity_usd": "v1", "lookback_return": "v1"},
}


def feature_policy_versions(policy_version: str) -> dict[str, str]:
    """Return the {feature_name: version} mapping for a known policy, failing closed on an unknown one."""
    if policy_version not in FEATURE_POLICIES:
        raise ValueError(f"unsupported feature policy version: {policy_version}")
    return FEATURE_POLICIES[policy_version]


def resolve_feature_definition(name: str, version: str, **kwargs) -> FeatureDefinition:
    """Resolve a catalog (name, version) pair to its canonical FeatureDefinition."""
    key = (name, version)
    if key not in _FEATURE_CATALOG:
        raise ValueError(f"unsupported feature identity: {name}@{version}")
    return _FEATURE_CATALOG[key](**kwargs)


def assert_feature_versions_compatible(name: str, version_a: str, version_b: str) -> None:
    """Fail closed unless two versions of the same named feature are declared comparable."""
    if version_a == version_b:
        return
    if version_b not in FEATURE_COMPATIBILITY.get((name, version_a), ()):
        raise ValueError(f"incompatible feature versions for {name}: {version_a} vs {version_b}")


# --- Labels -----------------------------------------------------------

# Declares which versions of the same label horizon's semantic contract are
# safe to compare. Mirrors FEATURE_COMPATIBILITY: empty until a second,
# explicitly declared-compatible semantic version of a horizon exists.
LABEL_COMPATIBILITY: dict[tuple[str, str], tuple[str, ...]] = {(horizon, "v1"): () for horizon in HORIZONS}


def assert_label_versions_compatible(horizon: str, version_a: str, version_b: str) -> None:
    """Fail closed unless two versions of the same horizon's label contract are declared comparable."""
    if version_a == version_b:
        return
    if version_b not in LABEL_COMPATIBILITY.get((horizon, version_a), ()):
        raise ValueError(f"incompatible label versions for {horizon}: {version_a} vs {version_b}")
