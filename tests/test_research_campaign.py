import json
import hashlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

from analysis.experiments import (ResearchCampaign, ResearchHypothesis, ResearchQuestion,
                                  ResearchRegistry, campaign_identity, load_campaign,
                                  verify_campaign, write_campaign)


def _registry():
    question = ResearchQuestion(
        claim="Liquidity predicts return", universe="fixture", treatment="liquidity",
        features=("liquidity",), outcomes=("1h",), temporal_availability="at t",
        confounders=("chain",), baseline="constant", minimum_effect="1%",
        statistical_policy="fixed", validation_policy="holdout", falsification_policy="permutation",
        failure_interpretation="no support", applicable_datasets=("dataset-fixture",),
        provenance={"source": "test"})
    hypothesis = ResearchHypothesis(
        question_id=question.question_id, claim=question.claim, treatment=question.treatment,
        features=question.features, outcome="1h", temporal_availability=question.temporal_availability,
        confounders=question.confounders, baseline=question.baseline, minimum_effect=question.minimum_effect,
        statistical_policy=question.statistical_policy, validation_policy=question.validation_policy,
        falsification_policy=question.falsification_policy, failure_interpretation=question.failure_interpretation,
        applicable_datasets=question.applicable_datasets, provenance={"source": "test"})
    return ResearchRegistry((question,), (hypothesis,)), question, hypothesis


def _campaign(registry, question, hypothesis, **overrides):
    values = dict(
        research_question_id=question.question_id, registry_identity=registry.identity(),
        dataset_identity="dataset-fixture", dataset_profile_identity="profile-fixture",
        hypothesis_ids=(hypothesis.hypothesis_id,), experiment_spec_ids=("spec-1",), run_ids=("run-1",),
        rejected_hypothesis_ids=(hypothesis.hypothesis_id,), promoted_hypothesis_ids=(),
        limitations=("fixture data only",), conclusion="The hypothesis was rejected.",
        artifact_identities={"registry": registry.identity(), "profile": "profile-fixture"},
        provenance={"source": "test"})
    values.update(overrides)
    return ResearchCampaign(**values)


def test_campaign_identity_and_outcomes_are_deterministic():
    registry, question, hypothesis = _registry()
    campaign = _campaign(registry, question, hypothesis)
    assert campaign.campaign_id == campaign_identity(campaign)
    assert campaign.campaign_id == _campaign(registry, question, hypothesis).campaign_id
    with pytest.raises(ValueError, match="disjoint"):
        _campaign(registry, question, hypothesis,
                  promoted_hypothesis_ids=(hypothesis.hypothesis_id,))


def test_campaign_artifact_is_immutable_and_replayable(tmp_path):
    registry, question, hypothesis = _registry()
    campaign = _campaign(registry, question, hypothesis)
    path = write_campaign(campaign, tmp_path)
    assert load_campaign(path) == campaign
    assert write_campaign(campaign, tmp_path) == path
    path.write_text("conflict", encoding="utf-8")
    with pytest.raises(FileExistsError, match="immutable research campaign"):
        write_campaign(campaign, tmp_path)


def test_campaign_verification_binds_registry_profile_and_runs(monkeypatch):
    registry, question, hypothesis = _registry()
    profile_body = {"dataset_identity": "dataset-fixture", "profile_version": "test"}
    profile = {**profile_body, "profile_identity": hashlib.sha256(
        (json.dumps(profile_body, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()}
    campaign = _campaign(registry, question, hypothesis,
                         dataset_profile_identity=profile["profile_identity"])
    run = SimpleNamespace(run_id="run-1", dataset_identity="dataset-fixture",
                          experiment_spec_id="spec-1", research_question_id=question.question_id,
                          research_hypothesis_id=hypothesis.hypothesis_id)
    monkeypatch.setattr("analysis.experiments.campaign.load_run", lambda path: run)
    assert verify_campaign(campaign, registry=registry, profile=profile, run_root="runs") == campaign
    with pytest.raises(ValueError, match="profile identity"):
        verify_campaign(campaign, registry=registry,
                        profile={**profile, "profile_identity": "wrong"}, run_root="runs")


def test_campaign_cli_validates_and_writes(tmp_path):
    registry, question, hypothesis = _registry()
    source = tmp_path / "campaign.json"
    source.write_text(json.dumps({**{
        "research_question_id": question.question_id, "registry_identity": registry.identity(),
        "dataset_identity": "dataset-fixture", "dataset_profile_identity": "profile-fixture",
        "hypothesis_ids": [hypothesis.hypothesis_id], "experiment_spec_ids": ["spec-1"],
        "run_ids": ["run-1"], "rejected_hypothesis_ids": [hypothesis.hypothesis_id],
        "promoted_hypothesis_ids": [], "limitations": ["fixture data only"],
        "conclusion": "rejected", "artifact_identities": {"registry": registry.identity()},
        "provenance": {"source": "test"}}}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "analysis.experiments", "validate-campaign", str(source)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["valid"] is True
    result = subprocess.run([sys.executable, "-m", "analysis.experiments", "write-campaign",
                             str(source), "--output", str(tmp_path / "campaigns")],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["campaign_id"]
