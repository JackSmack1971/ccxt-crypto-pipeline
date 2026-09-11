from __future__ import annotations

import math
from typing import Any


def compute_metrics(equity_ledger: tuple[dict[str, Any], ...] | list[dict[str, Any]], *,
                    trades: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
                    annualization_days: int = 365) -> dict[str, float | int | None]:
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
    returns = [(values[i] / values[i - 1]) - 1 for i in range(1, len(values)) if values[i - 1] != 0]
    peak = values[0]
    drawdowns = []
    for value in values:
        peak = max(peak, value)
        drawdowns.append(value / peak - 1 if peak else 0.0)
    mean = sum(returns) / len(returns) if returns else None
    volatility = math.sqrt(sum((x - mean) ** 2 for x in returns) / (len(returns) - 1)) * math.sqrt(annualization_days) if len(returns) > 1 else None
    sharpe = (mean / (volatility / math.sqrt(annualization_days))) * math.sqrt(annualization_days) if mean is not None and volatility not in (None, 0) else None
    total_fees = sum(float(trade.get("fee", 0.0)) for trade in trades)
    total_slippage = sum(float(trade.get("slippage", 0.0)) for trade in trades)
    return {"initial_equity": initial, "final_equity": final, "total_return": final / initial - 1 if initial else None,
            "max_drawdown": min(drawdowns), "volatility_annualized": volatility, "sharpe_annualized": sharpe,
            "total_fees": total_fees, "total_slippage": total_slippage,
            "observations": len(values), "annualization_days": annualization_days}
