"""Phase 6 governed experiment specification and deterministic execution.

``spec.py`` versions, cross-validates, and content-identifies a declarative
composition of the governed Phase 2-3 configuration objects; it never
executes cohort extraction, feature computation, labeling, splitting, or
candidate evaluation itself. ``runner.py`` is the first slice that actually
executes a spec: it composes the already-governed Phase 3 helpers in the
sequence the spec declares and writes one immutable run directory/manifest.
"""

from .runner import MANIFEST_VERSION, resolve_feature_registry, run_experiment
from .catalog import RunComparison, RunRecord, catalog_runs, compare_runs, load_run
from .hypotheses import (FAMILY_MANIFEST_VERSION, FamilyEvaluation, FrozenHypothesisFamily,
                         HypothesisIdentity, evaluate_hypothesis_family,
                         freeze_hypothesis_family)
from .spec import (BaselinePolicy, CandidateDefinition, CostPolicy, ExperimentSpec,
                   HypothesisFamily, SPEC_VERSION, SplitPolicy,
                   StressPolicy,
                   StabilityPolicy,
                   NegativeControlPolicy,
                   FalsificationPolicy, FALSIFICATION_METHODS,
                   SUPPORTED_BASELINE_FAMILIES, SUPPORTED_CONFIRMATION_CORRECTIONS,
                   SUPPORTED_DISCOVERY_CORRECTIONS, experiment_spec_dict, experiment_spec_from_dict,
                   experiment_spec_id)
from .control import (APPROVAL_VERSION, approve_experiment_run, execute_experiment,
                      inspect_experiment_run, load_experiment_spec, validate_experiment_spec)
from .walk_forward import (WalkForwardEvaluation, WalkForwardFold,
                           build_walk_forward_evaluation)
from .uncertainty import UncertaintyPolicy, bootstrap_mean
from .stress import STRESS_MATRIX_VERSION
from .stability import STABILITY_VERSION, build_stability_evidence
from .negative_controls import NEGATIVE_CONTROL_VERSION, build_negative_control_evidence
from .falsification import FALSIFICATION_VERSION, build_falsification_evidence
from .closure import CLOSURE_VERSION, build_validation_closure
from .research import (HYPOTHESIS_VERSION, QUESTION_VERSION, REGISTRY_VERSION,
                       ResearchHypothesis, ResearchQuestion, ResearchRegistry,
                       hypothesis_dict, hypothesis_identity, question_dict, question_identity,
                       research_hypothesis_from_dict,
                       research_question_from_dict, verify_registry, write_registry)

__all__ = [
    "BaselinePolicy", "CandidateDefinition", "CostPolicy", "ExperimentSpec",
    "HypothesisFamily", "SPEC_VERSION", "SplitPolicy", "StressPolicy", "StabilityPolicy", "NegativeControlPolicy",
    "SUPPORTED_BASELINE_FAMILIES", "SUPPORTED_CONFIRMATION_CORRECTIONS",
    "SUPPORTED_DISCOVERY_CORRECTIONS", "experiment_spec_dict", "experiment_spec_from_dict", "experiment_spec_id",
    "MANIFEST_VERSION", "resolve_feature_registry", "run_experiment",
    "FAMILY_MANIFEST_VERSION", "FamilyEvaluation", "FrozenHypothesisFamily",
    "HypothesisIdentity", "evaluate_hypothesis_family", "freeze_hypothesis_family",
    "RunComparison", "RunRecord", "catalog_runs", "compare_runs", "load_run",
    "APPROVAL_VERSION", "approve_experiment_run", "execute_experiment",
    "inspect_experiment_run", "load_experiment_spec", "validate_experiment_spec",
    "WalkForwardEvaluation", "WalkForwardFold", "build_walk_forward_evaluation",
    "UncertaintyPolicy", "bootstrap_mean",
    "STRESS_MATRIX_VERSION",
    "STABILITY_VERSION", "build_stability_evidence",
    "NEGATIVE_CONTROL_VERSION", "build_negative_control_evidence",
    "FALSIFICATION_VERSION", "FALSIFICATION_METHODS", "FalsificationPolicy",
    "build_falsification_evidence",
    "CLOSURE_VERSION", "build_validation_closure",
    "QUESTION_VERSION", "HYPOTHESIS_VERSION", "REGISTRY_VERSION", "ResearchQuestion",
    "ResearchHypothesis", "ResearchRegistry", "question_dict", "hypothesis_dict",
    "question_identity", "hypothesis_identity",
    "research_question_from_dict", "research_hypothesis_from_dict", "write_registry", "verify_registry",
]
