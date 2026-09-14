"""Offline, provenance-rich Phase 3 new-token research primitives."""

from .cohort import CohortConfig, CohortRow, extract_cohort
from .eligibility import ChainEligibility, EligibilityPolicy, evaluate_chain_eligibility
from .features import FeatureDefinition, FeatureRegistry, compute_features, feature_definition_id
from .labels import (HORIZONS, LABEL_SEMANTIC_VERSIONS, ConversionObservation, ConversionPolicy,
                     LabelDefinition, LabelRow, generate_labels, label_definition_id, normalize_usd_price)
from .registry import (FEATURE_COMPATIBILITY, FEATURE_POLICIES, LABEL_COMPATIBILITY,
                       assert_feature_versions_compatible, assert_label_versions_compatible,
                       feature_policy_versions, resolve_feature_definition)
from .evaluation import (CandidateResult, Hypothesis, HypothesisRegistry, PromotionDecision,
                         PromotionEvidence, PromotionPolicy, SplitResult,
                         apply_bh_fdr, apply_holm, build_split, descriptive_baseline, baseline_families,
                         evaluate_candidate_promotion, rank_candidates, score_candidate,
                         validate_temporal_alignment, baseline_comparison)
from .handoff import phase2_strategy_spec
from .report import research_report
from .artifacts import write_research_run

__all__ = [
    "CohortConfig", "CohortRow", "extract_cohort",
    "ChainEligibility", "EligibilityPolicy", "evaluate_chain_eligibility",
    "FeatureDefinition", "FeatureRegistry",
    "compute_features", "feature_definition_id", "HORIZONS", "LABEL_SEMANTIC_VERSIONS",
    "ConversionObservation", "ConversionPolicy", "LabelDefinition",
    "LabelRow", "generate_labels", "label_definition_id", "normalize_usd_price",
    "FEATURE_COMPATIBILITY", "FEATURE_POLICIES", "LABEL_COMPATIBILITY",
    "assert_feature_versions_compatible", "assert_label_versions_compatible",
    "feature_policy_versions", "resolve_feature_definition",
    "CandidateResult", "Hypothesis", "HypothesisRegistry", "PromotionDecision", "PromotionEvidence",
    "PromotionPolicy", "SplitResult", "apply_bh_fdr",
    "apply_holm", "build_split", "descriptive_baseline", "baseline_families", "baseline_comparison", "rank_candidates", "score_candidate",
    "evaluate_candidate_promotion", "validate_temporal_alignment", "phase2_strategy_spec", "research_report", "write_research_run",
]
