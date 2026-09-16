import json
import subprocess
import sys

import pytest

from analysis.experiments import (ResearchHypothesis, ResearchQuestion, ResearchRegistry,
                                  hypothesis_dict, hypothesis_identity, question_dict, question_identity,
                                  write_registry)
from analysis.experiments.spec import experiment_spec_from_dict, experiment_spec_id, experiment_spec_dict
from analysis.experiments import FalsificationPolicy
from test_phase6 import build_spec


def _question(**overrides):
    values = {
        "claim": "Launch liquidity predicts the 1h outcome.", "universe": "new EVM assets",
        "treatment": "launch_liquidity_usd", "features": ("launch_liquidity_usd",),
        "outcomes": ("1h forward return",), "temporal_availability": "available at launch",
        "confounders": ("chain",), "baseline": "no_trade", "minimum_effect": "5 percentage points",
        "statistical_policy": "BH q <= 0.05", "validation_policy": "chronological holdout",
        "falsification_policy": "label permutation and leave-chain-out",
        "failure_interpretation": "failure does not support the claim",
        "applicable_datasets": ("dataset-fixture",), "provenance": {"author": "fixture"},
    }
    values.update(overrides)
    return ResearchQuestion(**values)


def _hypothesis(question, **overrides):
    values = {
        "question_id": question.question_id, "claim": question.claim,
        "treatment": question.treatment, "features": question.features, "outcome": "24h",
        "temporal_availability": question.temporal_availability, "confounders": question.confounders,
        "baseline": question.baseline, "minimum_effect": question.minimum_effect,
        "statistical_policy": question.statistical_policy, "validation_policy": question.validation_policy,
        "falsification_policy": question.falsification_policy,
        "failure_interpretation": question.failure_interpretation,
        "applicable_datasets": question.applicable_datasets, "provenance": {"source": "question"},
    }
    values.update(overrides)
    return ResearchHypothesis(**values)


def test_question_and_hypothesis_ids_are_deterministic_and_distinct():
    question = _question()
    hypothesis = _hypothesis(question)
    assert question.question_id == _question().question_id == question_identity(question)
    assert hypothesis.hypothesis_id == _hypothesis(question).hypothesis_id == hypothesis_identity(hypothesis)
    assert hypothesis.hypothesis_id != question.question_id


def test_registry_validates_linkage_and_binds_spec_identity():
    question = _question()
    hypothesis = _hypothesis(question)
    registry = ResearchRegistry((question,), (hypothesis,))
    bound = registry.bind_experiment(build_spec(), hypothesis.hypothesis_id)
    assert bound.research_question_id == question.question_id
    assert bound.research_hypothesis_id == hypothesis.hypothesis_id
    assert experiment_spec_id(bound) != experiment_spec_id(build_spec())
    assert experiment_spec_from_dict(experiment_spec_dict(bound)) == bound


def test_registry_rejects_unknown_link_and_incomplete_binding():
    question = _question()
    with pytest.raises(ValueError, match="unknown question"):
        ResearchRegistry((question,), (_hypothesis(question, question_id="missing"),))
    with pytest.raises(ValueError, match="bound together"):
        build_spec(research_question_id="question-only")


def test_registry_rejects_falsification_policy_mismatch():
    question = _question()
    hypothesis = _hypothesis(question, falsification_methods=("known_null",))
    with pytest.raises(ValueError, match="falsification policy"):
        ResearchRegistry((question,), (hypothesis,)).bind_experiment(build_spec(falsification=FalsificationPolicy()),
                                                                      hypothesis.hypothesis_id)

    hypothesis = _hypothesis(question, falsification_methods=("known_null",),
                             falsification_inapplicable_methods=("known_null",))
    registry = ResearchRegistry((question,), (hypothesis,))
    assert registry.bind_experiment(build_spec(falsification=FalsificationPolicy(
        methods=("known_null",), inapplicable_methods=("known_null",))), hypothesis.hypothesis_id)


def test_registry_artifact_is_immutable_and_replayable(tmp_path):
    question = _question()
    registry = ResearchRegistry((question,), (_hypothesis(question),))
    path = write_registry(registry, tmp_path)
    assert json.loads(path.read_text()) ["registry_identity"] == path.parent.name
    assert write_registry(registry, tmp_path) == path
    path.write_text("conflict", encoding="utf-8")
    with pytest.raises(FileExistsError, match="immutable research registry"):
        write_registry(registry, tmp_path)


def test_registry_cli_validates_and_writes_json(tmp_path):
    question = _question()
    hypothesis = _hypothesis(question)
    question_path = tmp_path / "question.json"
    question_path.write_text(json.dumps({"claim": question.claim, "universe": question.universe,
        "treatment": question.treatment, "features": question.features, "outcomes": question.outcomes,
        "temporal_availability": question.temporal_availability, "confounders": question.confounders,
        "baseline": question.baseline, "minimum_effect": question.minimum_effect,
        "statistical_policy": question.statistical_policy, "validation_policy": question.validation_policy,
        "falsification_policy": question.falsification_policy,
        "failure_interpretation": question.failure_interpretation,
        "applicable_datasets": question.applicable_datasets, "provenance": question.provenance}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "analysis.experiments", "validate-question", str(question_path)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["question_id"] == question.question_id
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"questions": [question_dict(question)],
                                         "hypotheses": [hypothesis_dict(hypothesis)]}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "analysis.experiments", "write-registry",
                             str(registry_path), "--output", str(tmp_path / "registries")],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["registry_id"]
