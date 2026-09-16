"""Immutable, deterministic provenance contracts for research campaigns."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from analysis.datasets.snapshot import DatasetSnapshot
from analysis.datasets.profile import verify_dataset_profile

from .catalog import load_run
from .research import ResearchRegistry
from .runner import run_experiment
from .significance import SignificanceEvidenceBundle
from .spec import ExperimentSpec, experiment_spec_id


CAMPAIGN_VERSION = "phase8r-research-campaign-v1"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, default=str, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _required(label: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"research campaign {label} is required")
    return value.strip()


def _items(label: str, values: tuple[str, ...], *, required: bool = True) -> tuple[str, ...]:
    values = tuple(values)
    if (required and not values) or any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"research campaign {label} must contain non-blank identities")
    if len(set(values)) != len(values):
        raise ValueError(f"research campaign {label} must be unique")
    return tuple(sorted(value.strip() for value in values))


@dataclass(frozen=True)
class ResearchCampaign:
    """A provenance object binding one governed inquiry to its evidence."""

    research_question_id: str
    registry_identity: str
    dataset_identity: str
    dataset_profile_identity: str
    hypothesis_ids: tuple[str, ...]
    experiment_spec_ids: tuple[str, ...]
    run_ids: tuple[str, ...]
    rejected_hypothesis_ids: tuple[str, ...]
    promoted_hypothesis_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    conclusion: str
    artifact_identities: Mapping[str, str]
    provenance: Mapping[str, Any]
    campaign_id: str = ""
    version: str = CAMPAIGN_VERSION

    def __post_init__(self) -> None:
        if self.version != CAMPAIGN_VERSION:
            raise ValueError(f"unsupported research campaign version: {self.version}")
        for label in ("research_question_id", "registry_identity", "dataset_identity",
                      "dataset_profile_identity", "conclusion"):
            _required(label, getattr(self, label))
        for label in ("hypothesis_ids", "experiment_spec_ids", "run_ids"):
            object.__setattr__(self, label, _items(label, getattr(self, label)))
        for label in ("rejected_hypothesis_ids", "promoted_hypothesis_ids"):
            object.__setattr__(self, label, _items(label, getattr(self, label), required=False))
        known = set(self.hypothesis_ids)
        if not set(self.rejected_hypothesis_ids) <= known or not set(self.promoted_hypothesis_ids) <= known:
            raise ValueError("research campaign outcome hypotheses must be declared")
        if set(self.rejected_hypothesis_ids) & set(self.promoted_hypothesis_ids):
            raise ValueError("research campaign hypothesis outcomes must be disjoint")
        object.__setattr__(self, "limitations", _items("limitations", self.limitations))
        if not isinstance(self.artifact_identities, Mapping) or not self.artifact_identities:
            raise ValueError("research campaign artifact identities are required")
        if any(not isinstance(key, str) or not key.strip() or
               not isinstance(value, str) or not value.strip()
               for key, value in self.artifact_identities.items()):
            raise ValueError("research campaign artifact identities must be non-blank")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("research campaign provenance must be an object")
        if not self.campaign_id:
            object.__setattr__(self, "campaign_id", campaign_identity(self))
        elif self.campaign_id != campaign_identity(self):
            raise ValueError("research campaign identity mismatch")


def campaign_dict(campaign: ResearchCampaign) -> dict[str, Any]:
    return asdict(campaign)


def campaign_identity(campaign: ResearchCampaign) -> str:
    value = campaign_dict(campaign)
    value.pop("campaign_id")
    return hashlib.sha256(_canonical(value)).hexdigest()[:24]


def research_campaign_from_dict(value: Mapping[str, Any]) -> ResearchCampaign:
    try:
        return ResearchCampaign(
            **{**dict(value),
               "hypothesis_ids": tuple(value["hypothesis_ids"]),
               "experiment_spec_ids": tuple(value["experiment_spec_ids"]),
               "run_ids": tuple(value["run_ids"]),
               "rejected_hypothesis_ids": tuple(value.get("rejected_hypothesis_ids", ())),
               "promoted_hypothesis_ids": tuple(value.get("promoted_hypothesis_ids", ())),
               "limitations": tuple(value["limitations"])}
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid research campaign structure") from exc


def write_campaign(campaign: ResearchCampaign, output_dir: str | Path) -> Path:
    payload = campaign_dict(campaign)
    payload["campaign_id"] = campaign_identity(campaign)
    target = Path(output_dir) / payload["campaign_id"]
    target.mkdir(parents=True, exist_ok=True)
    path = target / "campaign.json"
    content = _canonical(payload)
    if path.exists() and path.read_bytes() != content:
        raise FileExistsError(f"immutable research campaign differs: {path}")
    if not path.exists():
        path.write_bytes(content)
    return path


def load_campaign(path: str | Path) -> ResearchCampaign:
    file_path = Path(path)
    if file_path.is_dir():
        file_path /= "campaign.json"
    try:
        campaign = research_campaign_from_dict(json.loads(file_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid research campaign artifact: {file_path}") from exc
    if file_path.parent.name != campaign.campaign_id or campaign_identity(campaign) != campaign.campaign_id:
        raise ValueError(f"research campaign identity mismatch: {file_path}")
    return campaign


def verify_campaign(campaign: ResearchCampaign, *, registry: ResearchRegistry,
                    profile: Mapping[str, Any], run_root: str | Path) -> ResearchCampaign:
    """Verify the campaign's declared registry, profile, and immutable runs."""
    if registry.identity() != campaign.registry_identity:
        raise ValueError("research campaign registry identity mismatch")
    question = registry.question(campaign.research_question_id)
    hypotheses = {item.hypothesis_id: item for item in registry.hypotheses}
    if not set(campaign.hypothesis_ids) <= set(hypotheses):
        raise ValueError("research campaign references an unknown hypothesis")
    if any(hypotheses[item].question_id != campaign.research_question_id
           for item in campaign.hypothesis_ids):
        raise ValueError("research campaign hypothesis question mismatch")
    if campaign.dataset_identity not in question.applicable_datasets:
        raise ValueError("research campaign dataset is not declared by the question")
    if profile.get("profile_identity") != campaign.dataset_profile_identity:
        raise ValueError("research campaign dataset profile identity mismatch")
    verify_dataset_profile(profile, campaign.dataset_identity)
    records = [load_run(Path(run_root) / run_id) for run_id in campaign.run_ids]
    if campaign.artifact_identities.get("registry") not in {None, registry.identity()}:
        raise ValueError("research campaign registry artifact identity mismatch")
    if campaign.artifact_identities.get("dataset_profile") not in {None, campaign.dataset_profile_identity}:
        raise ValueError("research campaign profile artifact identity mismatch")
    for record in records:
        declared = campaign.artifact_identities.get(f"run:{record.run_id}:manifest")
        if declared is not None:
            expected = hashlib.sha256((record.path / "manifest.json").read_bytes()).hexdigest()
            if declared != expected:
                raise ValueError("research campaign run artifact identity mismatch")
    if {record.run_id for record in records} != set(campaign.run_ids):
        raise ValueError("research campaign run identity mismatch")
    if any(record.dataset_identity != campaign.dataset_identity for record in records):
        raise ValueError("research campaign run dataset mismatch")
    if any(record.experiment_spec_id not in campaign.experiment_spec_ids for record in records):
        raise ValueError("research campaign run spec is not declared")
    if any(record.research_question_id != campaign.research_question_id for record in records):
        raise ValueError("research campaign run question mismatch")
    if any(record.research_hypothesis_id not in campaign.hypothesis_ids for record in records):
        raise ValueError("research campaign run hypothesis is not declared")
    for hypothesis_id in campaign.promoted_hypothesis_ids:
        record = next(record for record in records if record.research_hypothesis_id == hypothesis_id)
        promotion = json.loads((record.path / "promotion.json").read_text(encoding="utf-8"))
        closure = json.loads((record.path / "validation_closure.json").read_text(encoding="utf-8"))
        if promotion.get("state") != "holdout_confirmed" or closure.get("passed") is not True:
            raise ValueError("research campaign promoted outcome lacks complete holdout closure")
    return campaign


def execute_campaign(registry: ResearchRegistry, specs: tuple[ExperimentSpec, ...],
                     snapshot: DatasetSnapshot, profile: Mapping[str, Any], *,
                     run_root: str | Path, campaign_root: str | Path,
                     rejected_hypothesis_ids: tuple[str, ...] = (),
                     promoted_hypothesis_ids: tuple[str, ...] = (),
                     conclusion: str, limitations: tuple[str, ...],
                     provenance: Mapping[str, Any] | None = None,
                     significance_evidence: Mapping[str, SignificanceEvidenceBundle] | None = None,
                     confirmation_significance_evidence: Mapping[str, SignificanceEvidenceBundle] | None = None) -> Path:
    """Run one complete, locally replayable campaign through governed boundaries."""
    if not specs:
        raise ValueError("research campaign requires at least one experiment spec")
    verify_dataset_profile(profile, snapshot.dataset_identity)
    bound_specs = []
    for spec in specs:
        if spec.research_hypothesis_id is None:
            raise ValueError("campaign experiment specs must bind a research hypothesis")
        bound_specs.append(registry.bind_experiment(spec, spec.research_hypothesis_id))
    question_ids = {registry.hypothesis(spec.research_hypothesis_id).question_id
                    for spec in bound_specs}
    if len(question_ids) != 1:
        raise ValueError("campaign specs must belong to one research question")
    allowed_hypotheses = {spec.research_hypothesis_id for spec in bound_specs}
    for label, evidence in (("significance_evidence", significance_evidence),
                            ("confirmation_significance_evidence", confirmation_significance_evidence)):
        if evidence is not None and not set(evidence) <= allowed_hypotheses:
            raise ValueError(f"campaign {label} references an unknown hypothesis")

    def run_bound(spec: ExperimentSpec) -> Path:
        hypothesis_id = spec.research_hypothesis_id
        return run_experiment(
            spec, snapshot, run_root,
            significance_evidence=(significance_evidence or {}).get(hypothesis_id),
            confirmation_significance_evidence=(confirmation_significance_evidence or {}).get(hypothesis_id))

    run_paths = tuple(run_bound(spec) for spec in bound_specs)
    records = tuple(load_run(path) for path in run_paths)
    hypothesis_ids = tuple(record.research_hypothesis_id for record in records)
    if None in hypothesis_ids or len(set(hypothesis_ids)) != len(hypothesis_ids):
        raise ValueError("campaign specs must test each hypothesis at most once")
    spec_ids = tuple(experiment_spec_id(spec) for spec in bound_specs)
    artifact_identities = {
        "registry": registry.identity(),
        "dataset_profile": profile["profile_identity"],
        **{f"run:{record.run_id}:manifest": hashlib.sha256(
            (record.path / "manifest.json").read_bytes()).hexdigest() for record in records},
    }
    campaign = ResearchCampaign(
        research_question_id=next(iter(question_ids)), registry_identity=registry.identity(),
        dataset_identity=snapshot.dataset_identity,
        dataset_profile_identity=profile["profile_identity"], hypothesis_ids=tuple(hypothesis_ids),
        experiment_spec_ids=spec_ids, run_ids=tuple(record.run_id for record in records),
        rejected_hypothesis_ids=rejected_hypothesis_ids,
        promoted_hypothesis_ids=promoted_hypothesis_ids, limitations=limitations,
        conclusion=conclusion, artifact_identities=artifact_identities,
        provenance=provenance or {"execution": "local-governed-campaign"})
    verify_campaign(campaign, registry=registry, profile=profile, run_root=run_root)
    return write_campaign(campaign, campaign_root)


__all__ = ["CAMPAIGN_VERSION", "ResearchCampaign", "campaign_dict", "campaign_identity",
           "research_campaign_from_dict", "write_campaign", "load_campaign", "verify_campaign",
           "execute_campaign"]
