from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable

_NUMBER = re.compile(r"(?<![A-Za-z])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:%|[A-Za-z]{0,4})?(?![A-Za-z])")
_NUMBER_WORD = re.compile(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|dozen|couple|score)\b", re.I)
_COMPARE = re.compile(r"\b(?:more|less|higher|lower|greater|smaller|increase|decrease|outperform(?:ed|s)?|better|worse|versus|vs\.?|than|exceed(?:ed|s)?|surpass(?:ed|es)?|twice|half)\b", re.I)
_DURATION = re.compile(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*hour\b", re.I)
_DURATION_VALUES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


@dataclass(frozen=True)
class Evidence:
    artifact: str
    row: str | int | None
    dataset_identity: str
    query_config_identity: str
    time_range: dict[str, Any]
    uncertainty: Any = None
    side: str | None = None


@dataclass(frozen=True)
class Derivation:
    source_field: str
    operation: str = "identity"
    unit: str = ""
    source_unit: str = ""
    decimals: int = 6
    left_label: str = ""
    right_label: str = ""


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
        return bool(_NUMBER.search(self.text) or _NUMBER_WORD.search(self.text) or _COMPARE.search(self.text))


def _claim(value: Claim | dict[str, Any]) -> Claim:
    if isinstance(value, Claim):
        return value
    evidence = tuple(Evidence(**item) for item in value.get("evidence", ()))
    raw_derivation = value.get("derivation")
    derivation = Derivation(**raw_derivation) if raw_derivation is not None else None
    return Claim(value["id"], value["text"], value.get("kind", "fact"), evidence, derivation)


def _derived_value(claim: Claim, staged: dict[str, Any]) -> float:
    if claim.derivation is None:
        raise ValueError(f"numeric claim {claim.id} lacks a derivation")
    d = claim.derivation
    if d.operation not in {"identity", "mean", "difference", "ratio", "percent_change"}:
        raise ValueError(f"claim {claim.id} has unsupported derivation operation: {d.operation}")
    values = []
    for evidence in claim.evidence:
        rows = staged[evidence.artifact]
        if type(evidence.row) is not int or not isinstance(rows, list) or not 0 <= evidence.row < len(rows):
            raise ValueError(f"claim {claim.id} derivation references an invalid row")
        value = rows[evidence.row].get(d.source_field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"claim {claim.id} derivation source is not numeric: {d.source_field}")
        if not math.isfinite(float(value)):
            raise ValueError(f"claim {claim.id} derivation source is non-finite: {d.source_field}")
        values.append(float(value))
    if d.operation == "identity":
        if len(values) != 1:
            raise ValueError(f"claim {claim.id} identity derivation requires one evidence row")
        return values[0]
    if d.operation == "mean":
        return sum(values) / len(values) if values else 0.0
    if len(values) != 2:
        raise ValueError(f"claim {claim.id} {d.operation} derivation requires two evidence rows")
    if d.operation == "difference":
        result = values[0] - values[1]
        if not math.isfinite(result):
            raise ValueError(f"claim {claim.id} derivation is non-finite")
        return result
    if d.operation == "ratio":
        if values[1] == 0:
            raise ValueError(f"claim {claim.id} ratio has a zero denominator")
        result = values[0] / values[1]
        if not math.isfinite(result):
            raise ValueError(f"claim {claim.id} derivation is non-finite")
        return result
    if values[1] == 0:
        raise ValueError(f"claim {claim.id} percent_change has a zero denominator")
    result = (values[0] - values[1]) / values[1] * 100
    if not math.isfinite(result):
        raise ValueError(f"claim {claim.id} derivation is non-finite")
    return result


def _claim_numbers(text: str) -> list[float]:
    return [float(match.group(0).rstrip("%")) for match in _NUMBER.finditer(text)
            if match.group(0).rstrip("%").replace(".", "", 1).lstrip("+-").isdigit()]


def _unit_matches(text: str, unit: str) -> bool:
    markers = {"percent": ("%", "percent"), "percentage": ("%", "percent"),
               "usd": ("$", "usd", "dollar"), "dollars": ("$", "usd", "dollar"),
               "log-return": ("log-return", "log return")}
    expected = markers.get(unit.lower(), (unit.lower(), unit.lower().replace("-", " ")))
    lowered = text.lower()
    if re.search(r"\bnot\s+(?:an?\s+)?(?:" + "|".join(re.escape(marker) for marker in expected) + r")\b", lowered):
        return False
    number = _NUMBER.search(text)
    if number is None:
        return any(marker in lowered for marker in expected)
    nearby = lowered[max(0, number.start() - 12):number.end() + 12]
    if unit.lower() in {"usd", "dollars"} and ("%" in lowered or "percent" in lowered):
        return False
    if unit.lower() in {"percent", "percentage"} and any(marker in lowered for marker in ("$", "usd", "dollar")):
        return False
    if unit.lower() in {"ratio", "unitless"}:
        return not any(marker in lowered for marker in ("$", "%", "usd", "dollar", "percent"))
    if unit.lower() not in {"usd", "dollars", "percent", "percentage"}:
        return any(marker in lowered for marker in expected)
    return any(marker in nearby for marker in expected)


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
        if claim.factual:
            for evidence in claim.evidence:
                if evidence.artifact not in staged:
                    raise ValueError(f"claim {claim.id} references unstaged artifact {evidence.artifact}")
                expected_dataset = manifest.get("dataset_identity", manifest.get("inputs", {}).get("dataset_identity"))
                expected_config = manifest.get("query_config_identity", manifest.get("config_identity"))
                expected_range = manifest.get("time_range", manifest.get("inputs", {}).get("time_range", {}))
                if evidence.dataset_identity != expected_dataset:
                    raise ValueError(f"claim {claim.id} has mismatched dataset identity")
                if expected_config is not None and evidence.query_config_identity != expected_config:
                    raise ValueError(f"claim {claim.id} has mismatched query/config identity")
                if evidence.time_range != expected_range:
                    raise ValueError(f"claim {claim.id} has mismatched time range")
                if evidence.uncertainty is None:
                    raise ValueError(f"claim {claim.id} has incomplete provenance")
                if not expected_dataset or not expected_config or not expected_range or evidence.row is None:
                    raise ValueError(f"claim {claim.id} has incomplete provenance")
                if evidence.row is not None:
                    rows = staged[evidence.artifact]
                    if (not isinstance(rows, list) or type(evidence.row) is not int or
                            not 0 <= evidence.row < len(rows)):
                        raise ValueError(f"claim {claim.id} references missing row {evidence.row}")
        if claim.numeric_or_comparative:
            if not claim.evidence:
                raise ValueError(f"numeric or comparative claim has no evidence: {claim.id}")
            if claim.derivation is None:
                raise ValueError(f"numeric claim {claim.id} lacks a derivation")
            if (_COMPARE.search(claim.text) and
                    (claim.derivation.operation not in {"difference", "ratio", "percent_change"} or
                     len(claim.evidence) != 2 or
                     len({(item.artifact, item.row) for item in claim.evidence}) != 2 or
                     not claim.derivation.left_label or not claim.derivation.right_label)):
                raise ValueError(f"claim {claim.id} comparative derivation requires two evidence rows")
            if (_COMPARE.search(claim.text) and tuple(item.side for item in claim.evidence) !=
                    (claim.derivation.left_label, claim.derivation.right_label)):
                raise ValueError(f"claim {claim.id} comparative evidence sides do not match its derivation")
            if _COMPARE.search(claim.text) and "twice" in claim.text.lower() and (claim.derivation.operation != "ratio" or round(_derived_value(claim, staged), 12) != 2):
                raise ValueError(f"claim {claim.id} twice comparison disagrees with its derivation")
            if _COMPARE.search(claim.text) and "half" in claim.text.lower() and (claim.derivation.operation != "ratio" or round(_derived_value(claim, staged), 12) != 0.5):
                raise ValueError(f"claim {claim.id} half comparison disagrees with its derivation")
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
                if evidence.row is not None:
                    rows = staged[evidence.artifact]
                    if isinstance(rows, list) and (type(evidence.row) is not int or not 0 <= evidence.row < len(rows)):
                        raise ValueError(f"claim {claim.id} references missing row {evidence.row}")
                required = (evidence.dataset_identity, evidence.query_config_identity, evidence.time_range)
                if not required[0] or not required[1] or not required[2] or evidence.uncertainty is None:
                    raise ValueError(f"claim {claim.id} has incomplete provenance")
            expected = _derived_value(claim, staged)
            duration = _DURATION.search(claim.text)
            if duration:
                duration_hours = _DURATION_VALUES[duration.group(0).lower().replace("-", " ").split()[0]]
                for evidence in claim.evidence:
                    row = staged[evidence.artifact][evidence.row]
                    declared_horizon = row.get("horizon", row.get("timeframe"))
                    normalized_horizon = (declared_horizon.lower().replace("-", "").replace(" ", "")
                                          if isinstance(declared_horizon, str) else "")
                    if normalized_horizon not in {f"{duration_hours}h", f"{duration_hours}hour", f"{duration_hours}hours"}:
                        raise ValueError(f"claim {claim.id} duration is not supported by its evidence")
            decimals = claim.derivation.decimals
            if (decimals < 0 or decimals > 12 or claim.derivation.unit == "" or
                    claim.derivation.source_unit == ""):
                raise ValueError(f"claim {claim.id} has invalid formatting policy")
            if (claim.derivation.operation in {"identity", "difference"} and
                    claim.derivation.unit != claim.derivation.source_unit):
                raise ValueError(f"claim {claim.id} has incompatible source/output units")
            if claim.derivation.operation == "mean" and claim.derivation.unit != claim.derivation.source_unit:
                raise ValueError(f"claim {claim.id} has incompatible source/output units")
            if claim.derivation.operation == "ratio" and claim.derivation.unit.lower() not in {"ratio", "unitless"}:
                raise ValueError(f"claim {claim.id} has incompatible source/output units")
            if (claim.derivation.operation == "percent_change" and
                    claim.derivation.unit.lower() not in {"percent", "percentage"}):
                raise ValueError(f"claim {claim.id} has incompatible source/output units")
            numbers = _claim_numbers(claim.text)
            if _NUMBER_WORD.search(_DURATION.sub("", claim.text)):
                raise ValueError(f"claim {claim.id} contains an unsupported word-number representation")
            lowered = claim.text.lower()
            displayed_expected = (abs(expected) if any(word in lowered for word in ("lower", "less", "decrease")) and
                                  claim.derivation.operation in {"percent_change", "difference"} else expected)
            if numbers and (len(numbers) != 1 or round(numbers[0], decimals) != round(displayed_expected, decimals)):
                raise ValueError(f"claim {claim.id} rendered value disagrees with its derivation")
            if numbers:
                match = next(_NUMBER.finditer(claim.text))
                numeric_text = match.group(0).rstrip("%")
                if ((decimals > 0 and "." not in numeric_text) or
                        ("." in numeric_text and len(numeric_text.split(".", 1)[1]) != decimals)):
                    raise ValueError(f"claim {claim.id} rendered value disagrees with its formatting policy")
            if (numbers or _COMPARE.search(claim.text)) and not _unit_matches(claim.text, claim.derivation.unit):
                raise ValueError(f"claim {claim.id} has invalid formatting policy")
            if not numbers and not _COMPARE.search(claim.text):
                raise ValueError(f"claim {claim.id} rendered value disagrees with its derivation")
            if (_COMPARE.search(claim.text) and
                    not (lowered.find(claim.derivation.left_label.lower()) >= 0 and
                         lowered.find(claim.derivation.left_label.lower()) <
                         lowered.find(claim.derivation.right_label.lower()))):
                raise ValueError(f"claim {claim.id} comparative labels disagree with its derivation")
            if any(word in lowered for word in ("higher", "greater", "more", "outperform", "better", "increase", "increased", "exceed", "surpass")) and ((claim.derivation.operation == "ratio" and expected <= 1) or (claim.derivation.operation != "ratio" and expected <= 0)):
                raise ValueError(f"claim {claim.id} comparative direction disagrees with its derivation")
            if any(word in lowered for word in ("lower", "less", "smaller", "worse", "decrease", "decreased")) and ((claim.derivation.operation == "ratio" and expected >= 1) or (claim.derivation.operation != "ratio" and expected >= 0)):
                raise ValueError(f"claim {claim.id} comparative direction disagrees with its derivation")
        result.append({**asdict(claim), "evidence": [asdict(item) for item in claim.evidence],
                       "derivation": asdict(claim.derivation) if claim.derivation else None})
    return tuple(result)
