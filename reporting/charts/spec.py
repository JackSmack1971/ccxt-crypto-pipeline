from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any


@dataclass(frozen=True)
class ChartSpec:
    id: str
    data_artifact: str
    x_column: str
    y_column: str
    x_unit: str
    y_unit: str
    missing_behavior: str
    source_attribution: str
    alt_text: str
    transformations: tuple[str, ...] = ()
    annotations: tuple[dict[str, Any], ...] = ()
    width: int = 800
    height: int = 450


def _spec(value: ChartSpec | dict[str, Any]) -> ChartSpec:
    if isinstance(value, ChartSpec):
        return value
    return ChartSpec(**{**value, "transformations": tuple(value.get("transformations", ())),
                        "annotations": tuple(value.get("annotations", ()))})


def validate_chart(value: ChartSpec | dict[str, Any], staged: dict[str, Any],
                   approved_transformations: dict[str, Any] | None = None,
                   manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = _spec(value)
    if (not all(isinstance(getattr(spec, field), str) and getattr(spec, field)
                for field in ("id", "data_artifact", "x_column", "y_column", "x_unit", "y_unit",
                              "missing_behavior", "source_attribution", "alt_text")) or
            isinstance(spec.width, bool) or not isinstance(spec.width, int) or
            isinstance(spec.height, bool) or not isinstance(spec.height, int)):
        raise ValueError(f"chart {spec.id!r} has invalid field types")
    if not all((spec.id, spec.data_artifact, spec.x_column, spec.y_column, spec.x_unit,
                spec.y_unit, spec.missing_behavior, spec.source_attribution, len(spec.alt_text.strip()) >= 10)):
        raise ValueError(f"chart {spec.id!r} is missing required accessibility/provenance metadata")
    if spec.missing_behavior not in {"explicit_state", "fail"}:
        raise ValueError(f"chart {spec.id} has unsupported missing-data behavior")
    if spec.width < 320 or spec.width > 4096 or spec.height < 180 or spec.height > 4096:
        raise ValueError(f"chart {spec.id} dimensions are not readable")
    if any(item not in {"identity", "sort_x"} for item in spec.transformations):
        raise ValueError(f"chart {spec.id} has unsupported transformation")
    approved = (approved_transformations or {}).get(spec.id)
    if spec.transformations and (not isinstance(approved, (list, tuple)) or tuple(approved) != spec.transformations):
        raise ValueError(f"chart {spec.id} transformations are not approved by the result contract")
    for annotation in spec.annotations:
        if not isinstance(annotation, dict) or annotation.get("type") != "horizontal_line":
            raise ValueError(f"chart {spec.id} has unsupported annotation")
        if set(annotation) - {"type", "value", "label", "source", "evidence"}:
            raise ValueError(f"chart {spec.id} has unsupported annotation fields")
        if (isinstance(annotation.get("value"), bool) or not isinstance(annotation.get("value"), (int, float)) or
                not math.isfinite(annotation["value"]) or not isinstance(annotation.get("label"), str) or
                not annotation["label"] or not isinstance(annotation.get("source"), str) or
                not annotation["source"] or not isinstance(annotation.get("evidence"), dict)):
            raise ValueError(f"chart {spec.id} has incomplete annotation")
        evidence = annotation["evidence"]
        rows = staged.get(evidence.get("artifact"))
        if (not isinstance(rows, list) or type(evidence.get("row")) is not int or
                not 0 <= evidence["row"] < len(rows) or not evidence.get("field") or
                evidence["field"] not in rows[evidence["row"]]):
            raise ValueError(f"chart {spec.id} has invalid annotation evidence")
        observed = rows[evidence["row"]].get(evidence["field"])
        if (isinstance(observed, bool) or not isinstance(observed, (int, float)) or not math.isfinite(float(observed)) or
                observed != annotation["value"]):
            raise ValueError(f"chart {spec.id} annotation disagrees with its evidence")
        if evidence.get("unit") != spec.y_unit:
            raise ValueError(f"chart {spec.id} annotation has incompatible unit")
        if manifest is not None:
            expected_config = manifest.get("query_config_identity", manifest.get("config_identity"))
            if (evidence.get("dataset_identity") != manifest.get("dataset_identity") or
                    evidence.get("query_config_identity") != expected_config or
                    evidence.get("time_range") != manifest.get("time_range") or
                    evidence.get("uncertainty") is None):
                raise ValueError(f"chart {spec.id} has incomplete annotation provenance")
    rows = staged.get(spec.data_artifact)
    if not isinstance(rows, list):
        raise ValueError(f"chart {spec.id} references unstaged data: {spec.data_artifact}")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"chart {spec.id} contains malformed staged rows")
    if rows and (spec.x_column not in rows[0] or spec.y_column not in rows[0]):
        raise ValueError(f"chart {spec.id} references missing data columns")
    return asdict(spec)
