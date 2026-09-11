"""Small strategy boundary: strategies observe and express intentions only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from analysis.datasets.snapshot import Bar, Metadata


@dataclass(frozen=True)
class TargetPosition:
    canonical_id: str
    quantity: float


@dataclass(frozen=True)
class BarFrame:
    bar: Bar
    history: tuple[Bar, ...]
    metadata: Metadata | None


class Strategy(Protocol):
    name: str
    version: str

    def on_bar(self, frame: BarFrame) -> TargetPosition | None:
        """Return a target position; never a fill or cash mutation."""
