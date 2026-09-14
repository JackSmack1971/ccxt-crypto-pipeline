from __future__ import annotations

import math
from datetime import datetime
from typing import Any


def _interval_seconds(frequency: str) -> float:
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    if len(frequency) < 2 or frequency[-1] not in units:
        raise ValueError(f"unsupported observation frequency: {frequency}")
    try:
        count = int(frequency[:-1])
    except ValueError as exc:
        raise ValueError(f"unsupported observation frequency: {frequency}") from exc
    if count <= 0:
        raise ValueError(f"unsupported observation frequency: {frequency}")
    return count * units[frequency[-1]]


def compute_metrics(equity_ledger: tuple[dict[str, Any], ...] | list[dict[str, Any]], *,
                    trades: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
                    annualization_days: int = 365,
                    observation_frequency: str | None = None) -> dict[str, float | int | bool | str | None]:
    """Compute metrics solely from normalized equity rows."""
    if not equity_ledger:
        raise ValueError("cannot compute metrics from an empty equity ledger")
    if annualization_days <= 0:
        raise ValueError("annualization_days must be positive")
    values = [float(row["equity"]) for row in equity_ledger]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("equity ledger contains a non-finite value")
    initial = values[0]
    final = values[-1]
    timestamps = [datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00")) for row in equity_ledger]
    intervals = [(timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps))]
    if any(interval <= 0 for interval in intervals):
        raise ValueError("equity ledger timestamps must be strictly increasing")
    interval_seconds = _interval_seconds(observation_frequency) if observation_frequency else (
        sum(intervals) / len(intervals) if intervals else None)
    if interval_seconds is None:
        interval_seconds = 0.0
    irregular = bool(intervals and any(interval != intervals[0] for interval in intervals))
    annualization_periods = annualization_days * 86400 / interval_seconds if interval_seconds else None
    returns = [(values[i] / values[i - 1]) - 1 for i in range(1, len(values)) if values[i - 1] != 0]
    peak = values[0]
    drawdowns = []
    for value in values:
        peak = max(peak, value)
        drawdowns.append(value / peak - 1 if peak else 0.0)
    mean = sum(returns) / len(returns) if returns else None
    volatility = math.sqrt(sum((x - mean) ** 2 for x in returns) / (len(returns) - 1)) * math.sqrt(annualization_periods) if len(returns) > 1 and annualization_periods else None
    sharpe = (mean / (volatility / math.sqrt(annualization_periods))) * math.sqrt(annualization_periods) if mean is not None and volatility not in (None, 0) and annualization_periods else None
    total_fees = sum(float(trade.get("fee", 0.0)) for trade in trades)
    total_slippage = sum(float(trade.get("slippage", 0.0)) for trade in trades)
    return {"initial_equity": initial, "final_equity": final, "total_return": final / initial - 1 if initial else None,
            "max_drawdown": min(drawdowns), "volatility_annualized": volatility, "sharpe_annualized": sharpe,
            "total_fees": total_fees, "total_slippage": total_slippage,
            "observations": len(values), "annualization_days": annualization_days,
            "annualization_periods": annualization_periods,
            "observation_interval_seconds": interval_seconds or None,
            "irregular_intervals": irregular,
            "observation_frequency": observation_frequency}
