"""The smallest reference strategy used by fixture runs."""

from __future__ import annotations

from dataclasses import dataclass

from .protocol import BarFrame, TargetPosition


@dataclass(frozen=True)
class BuyAndHoldStrategy:
    quantity: float = 1.0
    name: str = "buy-and-hold"
    version: str = "1"

    def on_bar(self, frame: BarFrame) -> TargetPosition:
        return TargetPosition(frame.bar.canonical_id, self.quantity)
