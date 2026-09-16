"""Durable research-question and hypothesis declaration contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping


QUESTION_VERSION = "phase8r-research-question-v1"
HYPOTHESIS_VERSION = "phase8r-research-hypothesis-v1"
REGISTRY_VERSION = "phase8r-research-registry-v1"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode()


def _required(label: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"research {label} is required")
    return value.strip()


def _items(label: str, values: tuple[str, ...]) -> tuple[str, ...]:
    values = tuple(values)
    if not values or any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"research {label} requires at least one non-blank item")
    if len(set(values)) != len(values):
        raise ValueError(f"research {label} must be unique")
    return tuple(value.strip() for value in values)


def _declared_identity(value: Mapping[str, Any], field: str) -> str:
    payload = {key: item for key, item in value.items() if key != field}
    return hashlib.sha256(_canonical(payload)).hexdigest()[:24]


@dataclass(frozen=True)
class ResearchQuestion:
    """A durable question declaration, independent of any experiment result."""

    claim: str
    universe: str
    treatment: str
    features: tuple[str, ...]
    outcomes: tuple[str, ...]
    temporal_availability: str
    confounders: tuple[str, ...]
    baseline: str
    minimum_effect: str
    statistical_policy: str
    validation_policy: str
    falsification_policy: str
    failure_interpretation: str
    applicable_datasets: tuple[str, ...]
    provenance: Mapping[str, Any]
    question_id: str = ""
    version: str = QUESTION_VERSION

    def __post_init__(self) -> None:
        if self.version != QUESTION_VERSION:
            raise ValueError(f"unsupported research question version: {self.version}")
        for label in ("claim", "universe", "treatment", "temporal_availability", "baseline",
                      "minimum_effect", "statistical_policy", "validation_policy",
                      "falsification_policy", "failure_interpretation"):
            _required(label, getattr(self, label))
        for label in ("features", "outcomes", "confounders", "applicable_datasets"):
            object.__setattr__(self, label, _items(label, getattr(self, label)))
        if not isinstance(self.provenance, Mapping):
            raise ValueError("research question provenance must be an object")
        if not self.question_id:
            object.__setattr__(self, "question_id", _declared_identity(question_dict(self), "question_id"))
        elif not self.question_id.strip():
            raise ValueError("research question id cannot be blank")


@dataclass(frozen=True)
class ResearchHypothesis:
    """One testable hypothesis linked to exactly one declared question."""

    question_id: str
    claim: str
    treatment: str
    features: tuple[str, ...]
    outcome: str
    temporal_availability: str
    confounders: tuple[str, ...]
    baseline: str
    minimum_effect: str
    statistical_policy: str
    validation_policy: str
    falsification_policy: str
    failure_interpretation: str
    applicable_datasets: tuple[str, ...]
    provenance: Mapping[str, Any]
    hypothesis_id: str = ""
    version: str = HYPOTHESIS_VERSION
    falsification_methods: tuple[str, ...] = ()
    falsification_inapplicable_methods: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.version != HYPOTHESIS_VERSION:
            raise ValueError(f"unsupported research hypothesis version: {self.version}")
        _required("hypothesis question_id", self.question_id)
        for label in ("claim", "treatment", "outcome", "temporal_availability", "baseline",
                      "minimum_effect", "statistical_policy", "validation_policy",
                      "falsification_policy", "failure_interpretation"):
            _required(label, getattr(self, label))
        for label in ("features", "confounders", "applicable_datasets"):
            object.__setattr__(self, label, _items(label, getattr(self, label)))
        if any(not isinstance(value, str) or not value.strip() for value in self.falsification_methods):
            raise ValueError("research hypothesis falsification methods must be non-blank")
        if len(set(self.falsification_methods)) != len(self.falsification_methods):
            raise ValueError("research hypothesis falsification methods must be unique")
        if (any(value not in self.falsification_methods for value in self.falsification_inapplicable_methods) or
                len(set(self.falsification_inapplicable_methods)) != len(self.falsification_inapplicable_methods)):
            raise ValueError("research hypothesis inapplicable methods must be declared and unique")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("research hypothesis provenance must be an object")
        if not self.hypothesis_id:
            object.__setattr__(self, "hypothesis_id", _declared_identity(hypothesis_dict(self), "hypothesis_id"))
        elif not self.hypothesis_id.strip():
            raise ValueError("research hypothesis id cannot be blank")


def question_dict(question: ResearchQuestion) -> dict[str, Any]:
    return asdict(question)


def hypothesis_dict(hypothesis: ResearchHypothesis) -> dict[str, Any]:
    return asdict(hypothesis)


def research_question_from_dict(value: Mapping[str, Any]) -> ResearchQuestion:
    try:
        return ResearchQuestion(**{**dict(value), "features": tuple(value["features"]),
                                  "outcomes": tuple(value["outcomes"]),
                                  "confounders": tuple(value["confounders"]),
                                  "applicable_datasets": tuple(value["applicable_datasets"])})
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid research question structure") from exc


def research_hypothesis_from_dict(value: Mapping[str, Any]) -> ResearchHypothesis:
    try:
        return ResearchHypothesis(**{**dict(value), "features": tuple(value["features"]),
                                    "confounders": tuple(value["confounders"]),
                                    "applicable_datasets": tuple(value["applicable_datasets"]),
                                    "falsification_methods": tuple(value.get("falsification_methods", ())),
                                    "falsification_inapplicable_methods": tuple(value.get("falsification_inapplicable_methods", ()))})
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid research hypothesis structure") from exc


def question_identity(question: ResearchQuestion) -> str:
    return _declared_identity(question_dict(question), "question_id")


def hypothesis_identity(hypothesis: ResearchHypothesis) -> str:
    return _declared_identity(hypothesis_dict(hypothesis), "hypothesis_id")


@dataclass(frozen=True)
class ResearchRegistry:
    """Validated, deterministic collection of questions and hypotheses."""

    questions: tuple[ResearchQuestion, ...] = ()
    hypotheses: tuple[ResearchHypothesis, ...] = ()

    def __post_init__(self) -> None:
        questions = tuple(self.questions)
        hypotheses = tuple(self.hypotheses)
        qids = [item.question_id for item in questions]
        hids = [item.hypothesis_id for item in hypotheses]
        if any(not item for item in qids) or len(set(qids)) != len(qids):
            raise ValueError("research question ids must be present and unique")
        if any(not item for item in hids) or len(set(hids)) != len(hids):
            raise ValueError("research hypothesis ids must be present and unique")
        known = set(qids)
        if any(item.question_id not in known for item in hypotheses):
            raise ValueError("research hypothesis references an unknown question")
        object.__setattr__(self, "questions", tuple(sorted(questions, key=lambda item: item.question_id)))
        object.__setattr__(self, "hypotheses", tuple(sorted(hypotheses, key=lambda item: item.hypothesis_id)))

    def question(self, question_id: str) -> ResearchQuestion:
        matches = [item for item in self.questions if item.question_id == question_id]
        if len(matches) != 1:
            raise ValueError(f"unknown research question: {question_id}")
        return matches[0]

    def hypothesis(self, hypothesis_id: str) -> ResearchHypothesis:
        matches = [item for item in self.hypotheses if item.hypothesis_id == hypothesis_id]
        if len(matches) != 1:
            raise ValueError(f"unknown research hypothesis: {hypothesis_id}")
        return matches[0]

    def bind_experiment(self, spec: Any, hypothesis_id: str) -> Any:
        """Bind a validated experiment spec to a declared question and hypothesis."""
        hypothesis = self.hypothesis(hypothesis_id)
        question = self.question(hypothesis.question_id)
        if any(feature not in spec.feature_set for feature in hypothesis.features):
            raise ValueError("experiment spec does not declare every hypothesis feature")
        if spec.candidate.horizon not in hypothesis.outcome:
            raise ValueError("experiment candidate horizon is not declared by the hypothesis outcome")
        if hypothesis.falsification_methods and (
                tuple(spec.falsification.methods) != tuple(hypothesis.falsification_methods) or
                tuple(spec.falsification.inapplicable_methods) != tuple(
                    hypothesis.falsification_inapplicable_methods)):
            raise ValueError("experiment falsification policy does not match the hypothesis")
        return replace(spec, research_question_id=question.question_id,
                       research_hypothesis_id=hypothesis.hypothesis_id)

    def registry_dict(self) -> dict[str, Any]:
        return {"registry_version": REGISTRY_VERSION,
                "questions": [question_dict(item) for item in self.questions],
                "hypotheses": [hypothesis_dict(item) for item in self.hypotheses]}

    def identity(self) -> str:
        return hashlib.sha256(_canonical(self.registry_dict())).hexdigest()[:24]


def write_registry(registry: ResearchRegistry, output_dir: str | Path) -> Path:
    payload = registry.registry_dict()
    payload["registry_identity"] = registry.identity()
    target = Path(output_dir) / payload["registry_identity"]
    target.mkdir(parents=True, exist_ok=True)
    path = target / "registry.json"
    content = _canonical(payload)
    if path.exists() and path.read_bytes() != content:
        raise FileExistsError(f"immutable research registry differs: {path}")
    if not path.exists():
        path.write_bytes(content)
    return path


def verify_registry(registry: ResearchRegistry, registry_identity: str) -> str:
    if registry.identity() != registry_identity:
        raise ValueError("research registry identity mismatch")
    return registry_identity


__all__ = ["QUESTION_VERSION", "HYPOTHESIS_VERSION", "REGISTRY_VERSION", "ResearchQuestion",
           "ResearchHypothesis", "ResearchRegistry", "question_dict", "hypothesis_dict",
           "research_question_from_dict", "research_hypothesis_from_dict", "question_identity",
           "hypothesis_identity", "write_registry", "verify_registry"]
