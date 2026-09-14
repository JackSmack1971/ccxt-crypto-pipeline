"""Offline, provenance-rich Phase 3 new-token research primitives."""

from .cohort import CohortConfig, CohortRow, extract_cohort
from .eligibility import ChainEligibility, EligibilityPolicy, evaluate_chain_eligibility
from .features import FeatureDefinition, FeatureRegistry, compute_features
from .labels import (HORIZONS, ConversionObservation, ConversionPolicy, LabelDefinition,
                     LabelRow, generate_labels, normalize_usd_price)
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
    "compute_features", "HORIZONS", "ConversionObservation", "ConversionPolicy", "LabelDefinition",
    "LabelRow", "generate_labels", "normalize_usd_price",
    "CandidateResult", "Hypothesis", "HypothesisRegistry", "PromotionDecision", "PromotionEvidence",
    "PromotionPolicy", "SplitResult", "apply_bh_fdr",
    "apply_holm", "build_split", "descriptive_baseline", "baseline_families", "baseline_comparison", "rank_candidates", "score_candidate",
    "evaluate_candidate_promotion", "validate_temporal_alignment", "phase2_strategy_spec", "research_report", "write_research_run",
]
