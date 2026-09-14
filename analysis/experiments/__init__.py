"""Phase 6 governed experiment specification.

A versioned, declarative composition of the governed Phase 2-3 configuration
objects that together define one reproducible research experiment. This
module only versions, cross-validates, and content-identifies configuration;
it does not execute cohort extraction, feature computation, labeling,
splitting, or candidate evaluation (that remains Slice 6.2).
"""

from .spec import (BaselinePolicy, CandidateDefinition, CostPolicy, ExperimentSpec,
                   HypothesisFamily, SPEC_VERSION, SplitPolicy,
                   SUPPORTED_BASELINE_FAMILIES, SUPPORTED_CONFIRMATION_CORRECTIONS,
                   SUPPORTED_DISCOVERY_CORRECTIONS, experiment_spec_dict, experiment_spec_id)

__all__ = [
    "BaselinePolicy", "CandidateDefinition", "CostPolicy", "ExperimentSpec",
    "HypothesisFamily", "SPEC_VERSION", "SplitPolicy",
    "SUPPORTED_BASELINE_FAMILIES", "SUPPORTED_CONFIRMATION_CORRECTIONS",
    "SUPPORTED_DISCOVERY_CORRECTIONS", "experiment_spec_dict", "experiment_spec_id",
]
