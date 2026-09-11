"""Deterministic, bar-driven portfolio simulation."""

from .simulator import BacktestConfig, BacktestResult, simulate

__all__ = ["BacktestConfig", "BacktestResult", "simulate"]
