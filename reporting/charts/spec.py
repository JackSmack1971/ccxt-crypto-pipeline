from __future__ import annotations

from dataclasses import dataclass, asdict
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


def validate_chart(value: ChartSpec | dict[str, Any], staged: dict[str, Any]) -> dict[str, Any]:
    spec = _spec(value)
    if not all((spec.id, spec.data_artifact, spec.x_column, spec.y_column, spec.x_unit,
                spec.y_unit, spec.missing_behavior, spec.source_attribution, spec.alt_text)):
        raise ValueError(f"chart {spec.id!r} is missing required accessibility/provenance metadata")
    if spec.missing_behavior not in {"explicit_state", "fail"}:
        raise ValueError(f"chart {spec.id} has unsupported missing-data behavior")
    unsupported = [item for item in spec.transformations if item != "identity"]
    if unsupported:
        raise ValueError(f"chart {spec.id} has unsupported transformation: {unsupported[0]}")
    if spec.annotations:
        raise ValueError(f"chart {spec.id} has unsupported annotation")
    if spec.width < 320 or spec.height < 180:
        raise ValueError(f"chart {spec.id} dimensions are not readable")
    rows = staged.get(spec.data_artifact)
    if rows is None:
        raise ValueError(f"chart {spec.id} references unstaged data: {spec.data_artifact}")
    if rows and (spec.x_column not in rows[0] or spec.y_column not in rows[0]):
        raise ValueError(f"chart {spec.id} references missing data columns")
    return asdict(spec)
