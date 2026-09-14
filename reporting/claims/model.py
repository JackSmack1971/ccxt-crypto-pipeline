from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
class Derivation:
    evidence_index: int
    source_field: str
    operation: str
    source_unit: str
    result_unit: str
    decimals: int
    suffix: str = ""
    expected: str = ""
    baseline_field: str | None = None


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    kind: str = "fact"
    evidence: tuple[Evidence, ...] = ()
    derivation: Derivation | None = None

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
    raw_derivation = value.get("derivation")
    derivation = Derivation(**raw_derivation) if raw_derivation is not None else None
    return Claim(value["id"], value["text"], value.get("kind", "fact"), evidence, derivation)


def _row(staged: dict[str, Any], evidence: Evidence, claim_id: str) -> dict[str, Any]:
    rows = staged[evidence.artifact]
    if not isinstance(rows, list) or not isinstance(evidence.row, int) or not 0 <= evidence.row < len(rows):
        raise ValueError(f"claim {claim_id} derivation requires one existing indexed row")
    row = rows[evidence.row]
    if not isinstance(row, dict):
        raise ValueError(f"claim {claim_id} source row is not an object")
    return row


def _derive(claim: Claim, staged: dict[str, Any]) -> dict[str, Any]:
    derivation = claim.derivation
    if derivation is None:
        raise ValueError(f"numeric or comparative claim lacks a derivation: {claim.id}")
    if derivation.operation not in {"identity", "compare"}:
        raise ValueError(f"claim {claim.id} has unsupported derivation operation: {derivation.operation}")
    if derivation.source_unit != derivation.result_unit:
        raise ValueError(f"claim {claim.id} derivation has incompatible units")
    if not 0 <= derivation.evidence_index < len(claim.evidence):
        raise ValueError(f"claim {claim.id} derivation references missing evidence")
    if not 0 <= derivation.decimals <= 12 or derivation.suffix not in {"", "%"}:
        raise ValueError(f"claim {claim.id} has unsupported formatting policy")
    evidence = claim.evidence[derivation.evidence_index]
    source = _row(staged, evidence, claim.id)
    if derivation.source_field not in source or source[derivation.source_field] is None:
        raise ValueError(f"claim {claim.id} derivation source is unavailable")
    try:
        value = Decimal(str(source[derivation.source_field]))
    except (InvalidOperation, ValueError):
        raise ValueError(f"claim {claim.id} derivation source is not numeric") from None
    if derivation.operation == "compare":
        if not derivation.baseline_field or source.get(derivation.baseline_field) is None:
            raise ValueError(f"claim {claim.id} comparison baseline is unavailable")
        try:
            baseline = Decimal(str(source[derivation.baseline_field]))
        except (InvalidOperation, ValueError):
            raise ValueError(f"claim {claim.id} comparison baseline is not numeric") from None
        rendered = "higher" if value > baseline else "lower" if value < baseline else "equal"
    else:
        quantum = Decimal(1).scaleb(-derivation.decimals)
        rendered = f"{value.quantize(quantum, rounding=ROUND_HALF_UP):.{derivation.decimals}f}{derivation.suffix}"
    if derivation.expected != rendered:
        raise ValueError(f"claim {claim.id} declared value does not match its evidence derivation")
    matches = _NUMBER.findall(claim.text) if derivation.operation == "identity" else re.findall(r"\b(?:higher|lower|equal)\b", claim.text, re.I)
    if [item.lower() for item in matches] != [rendered.lower()]:
        raise ValueError(f"claim {claim.id} rendered value does not match its evidence derivation")
    return {**asdict(derivation), "derived_value": str(value), "rendered_value": rendered}


def validate_claims(claims: Iterable[Claim | dict[str, Any]], manifest: dict[str, Any],
                    staged: dict[str, Any] | None = None) -> tuple[dict[str, Any], ...]:
    """Validate provenance and declared evidence derivations before rendering."""
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
        derived = None
        if claim.factual and claim.numeric_or_comparative:
            for evidence in claim.evidence:
                if evidence.artifact not in staged:
                    raise ValueError(f"claim {claim.id} references unstaged artifact {evidence.artifact}")
                expected_dataset = manifest.get("dataset_identity", manifest.get("inputs", {}).get("dataset_identity"))
                expected_config = manifest.get("query_config_identity", manifest.get("config_identity"))
                if evidence.dataset_identity != expected_dataset:
                    raise ValueError(f"claim {claim.id} has mismatched dataset identity")
                if expected_config is not None and evidence.query_config_identity != expected_config:
                    raise ValueError(f"claim {claim.id} has mismatched query/config identity")
                expected_range = manifest.get("time_range", manifest.get("inputs", {}).get("time_range", {}))
                if evidence.time_range != expected_range:
                    raise ValueError(f"claim {claim.id} has mismatched time range")
                required = (evidence.dataset_identity, evidence.query_config_identity, evidence.time_range)
                if not required[0] or not required[1] or not required[2] or evidence.uncertainty is None:
                    raise ValueError(f"claim {claim.id} has incomplete provenance")
            derived = _derive(claim, staged)
        item = {**asdict(claim), "evidence": [asdict(entry) for entry in claim.evidence]}
        item["derivation"] = derived
        result.append(item)
    return tuple(result)
