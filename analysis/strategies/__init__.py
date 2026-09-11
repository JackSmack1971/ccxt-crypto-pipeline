"""Intention-only strategy interfaces."""

from .protocol import BarFrame, Strategy, TargetPosition
from .reference import BuyAndHoldStrategy

__all__ = ["BarFrame", "Strategy", "TargetPosition", "BuyAndHoldStrategy"]
