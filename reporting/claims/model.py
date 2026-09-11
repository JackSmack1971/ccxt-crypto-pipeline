from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable

_NUMBER = re.compile(r"(?<![A-Za-z])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:%|[A-Za-z]{0,4})?(?![A-Za-z])")
_COMPARE = re.compile(r"\b(?:more|less|higher|lower|greater|smaller|increase|decrease|outperform|better|worse|versus|vs\.?|than)\b", re.I)


@dataclass(frozen=True)
class Evidence:
    artifact: str
    row: str | int | None
    dataset_identity: str
    query_config_identity: str
    time_range: dict[str, Any]
    uncertainty: Any = None


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    kind: str = "fact"
    evidence: tuple[Evidence, ...] = ()

    @property
    def factual(self) -> bool:
        return self.kind == "fact"

    @property
    def numeric_or_comparative(self) -> bool:
        return bool(_NUMBER.search(self.text) or _COMPARE.search(self.text))


def _claim(value: Claim | dict[str, Any]) -> Claim:
    if isinstance(value, Claim):
        return value
    evidence = tuple(Evidence(**item) for item in value.get("evidence", ()))
    return Claim(value["id"], value["text"], value.get("kind", "fact"), evidence)


def validate_claims(claims: Iterable[Claim | dict[str, Any]], manifest: dict[str, Any],
                    staged: dict[str, Any] | None = None) -> tuple[dict[str, Any], ...]:
    """Validate the claim ledger before any prose is rendered."""
    staged = staged or {}
    result = []
    ids = set()
    for raw in claims:
        claim = _claim(raw)
        if claim.id in ids or not claim.text.strip():
            raise ValueError(f"invalid or duplicate claim: {claim.id!r}")
        ids.add(claim.id)
        if claim.kind not in {"fact", "interpretation"}:
            raise ValueError(f"unsupported claim kind: {claim.kind}")
        if claim.factual and not claim.evidence:
            raise ValueError(f"factual claim has no evidence: {claim.id}")
        if claim.factual and claim.numeric_or_comparative:
            for evidence in claim.evidence:
                if evidence.artifact not in staged and evidence.artifact not in manifest.get("artifacts", {}):
                    raise ValueError(f"claim {claim.id} references unstaged artifact {evidence.artifact}")
                if evidence.artifact in staged and evidence.row is not None:
                    rows = staged[evidence.artifact]
                    if isinstance(rows, list) and (not isinstance(evidence.row, int) or not 0 <= evidence.row < len(rows)):
                        raise ValueError(f"claim {claim.id} references missing row {evidence.row}")
                required = (evidence.dataset_identity, evidence.query_config_identity, evidence.time_range)
                if not required[0] or not required[1] or not required[2] or evidence.uncertainty is None:
                    raise ValueError(f"claim {claim.id} has incomplete provenance")
        result.append({**asdict(claim), "evidence": [asdict(item) for item in claim.evidence]})
    return tuple(result)
