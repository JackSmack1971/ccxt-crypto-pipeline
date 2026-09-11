"""Next-available-bar-open simulator with explicit ledgers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import math
from typing import Any

from analysis.datasets.snapshot import DatasetSnapshot
from analysis.strategies.protocol import BarFrame, Strategy


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 10_000.0
    fee_rate: float = 0.001
    slippage_bps: float = 0.0
    execution: str = "next_bar_open"
    missing_bar_policy: str = "skip"
    halted_bar_policy: str = "skip"
    stale_signal_policy: str = "execute_next_available"
    quote_currency: str = "USD"
    source_type: str = "cex"
    venue: str | None = None

    def validate(self) -> None:
        if self.execution != "next_bar_open":
            raise ValueError("unsupported execution assumption; only next_bar_open is supported")
        if self.initial_cash < 0 or self.fee_rate < 0 or self.slippage_bps < 0:
            raise ValueError("initial_cash, fee_rate, and slippage_bps must be non-negative")
        if self.missing_bar_policy not in {"skip", "error"} or self.halted_bar_policy not in {"skip", "error"}:
            raise ValueError("bar policies must be 'skip' or 'error'")
        if self.stale_signal_policy not in {"execute_next_available", "skip", "error"}:
            raise ValueError("stale_signal_policy must be 'execute_next_available', 'skip', or 'error'")
        if self.source_type != "cex":
            raise ValueError("unsupported execution universe; only CEX assets are supported")


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[dict[str, Any], ...]
    equity: tuple[dict[str, Any], ...]
    orders: tuple[dict[str, Any], ...]
    config: BacktestConfig


def _bar_interval(timeframe: str) -> timedelta:
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    if len(timeframe) < 2 or timeframe[-1] not in units:
        raise ValueError(f"unsupported timeframe for gap detection: {timeframe}")
    try:
        count = int(timeframe[:-1])
    except ValueError as exc:
        raise ValueError(f"unsupported timeframe for gap detection: {timeframe}") from exc
    if count <= 0:
        raise ValueError(f"unsupported timeframe for gap detection: {timeframe}")
    return timedelta(seconds=count * units[timeframe[-1]])


def simulate(dataset: DatasetSnapshot, strategy: Strategy, config: BacktestConfig | None = None) -> BacktestResult:
    config = config or BacktestConfig()
    config.validate()
    bars = dataset.all_bars()
    if not bars:
        raise ValueError("insufficient bars: dataset contains no eligible bars")
    assets = {asset.canonical_id: asset for asset in dataset.assets}
    selected = [assets[bar.canonical_id] for bar in bars]
    if any(asset.source_type != config.source_type for asset in selected):
        raise ValueError("unsupported execution universe: first slice supports CEX assets only")
    venues = {asset.chain_or_exchange for asset in selected}
    if config.venue is not None and venues - {config.venue}:
        raise ValueError(f"asset bars include a venue outside configured venue {config.venue!r}")
    if config.venue is None and len(venues) > 1:
        raise ValueError("cross-venue execution is unsupported; configure one CEX venue")
    if config.missing_bar_policy == "error":
        for asset_id in sorted({bar.canonical_id for bar in bars}):
            asset_bars = [bar for bar in bars if bar.canonical_id == asset_id]
            for previous, current in zip(asset_bars, asset_bars[1:]):
                if current.timestamp - previous.timestamp > _bar_interval(previous.timeframe):
                    raise ValueError(f"missing bar for {asset_id} between {previous.timestamp.isoformat()} and {current.timestamp.isoformat()}")
    cash = config.initial_cash
    positions: dict[str, float] = {}
    last_close: dict[str, float] = {}
    pending: dict[str, tuple[datetime, float, datetime]] = {}
    trades: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    equity: list[dict[str, Any]] = []
    history: dict[str, tuple] = {}

    if config.missing_bar_policy == "skip":
        for asset_id in sorted({bar.canonical_id for bar in bars}):
            asset_bars = [bar for bar in bars if bar.canonical_id == asset_id]
            for previous, current in zip(asset_bars, asset_bars[1:]):
                if current.timestamp - previous.timestamp > _bar_interval(previous.timeframe):
                    orders.append({"canonical_id": asset_id, "status": "skipped_missing",
                                   "from": previous.timestamp.isoformat(), "to": current.timestamp.isoformat()})

    index = 0
    while index < len(bars):
        timestamp = bars[index].timestamp
        end = index + 1
        while end < len(bars) and bars[end].timestamp == timestamp:
            end += 1
        timestamp_bars = bars[index:end]
        for bar in timestamp_bars:
            previous = history.get(bar.canonical_id, ())
            is_gap = bool(previous and bar.timestamp - previous[-1].timestamp > _bar_interval(previous[-1].timeframe))
            if is_gap and bar.canonical_id in pending:
                if config.stale_signal_policy == "error":
                    signal_time = pending[bar.canonical_id][0]
                    raise ValueError(f"stale signal for {bar.canonical_id}: missing bars after {signal_time.isoformat()}")
                if config.stale_signal_policy == "skip":
                    signal_time, _target, _ = pending.pop(bar.canonical_id)
                    orders.append({"canonical_id": bar.canonical_id, "signal_time": signal_time.isoformat(),
                                   "execution_time": bar.timestamp.isoformat(), "status": "skipped_stale_signal"})
            if bar.halted:
                if config.halted_bar_policy == "error":
                    raise ValueError(f"halted bar encountered for {bar.canonical_id} at {bar.timestamp.isoformat()}")
                orders.append({"canonical_id": bar.canonical_id, "status": "skipped_halted", "timestamp": bar.timestamp.isoformat()})
                continue
            if any(price <= 0 for price in (bar.open, bar.high, bar.low, bar.close)):
                raise ValueError(f"bar contains a non-positive price: {bar.canonical_id} at {bar.timestamp.isoformat()}")
            last_close[bar.canonical_id] = bar.close
            if bar.canonical_id in pending:
                signal_time, target, _ = pending.pop(bar.canonical_id)
                current = positions.get(bar.canonical_id, 0.0)
                delta = target - current
                if delta != 0:
                    direction = 1 if delta > 0 else -1
                    price = bar.open * (1 + direction * config.slippage_bps / 10000)
                    notional = abs(delta) * price
                    fee = notional * config.fee_rate
                    slippage = abs(delta) * bar.open * config.slippage_bps / 10000
                    total_buy = notional + fee
                    if direction > 0 and total_buy > cash + 1e-12:
                        orders.append({"canonical_id": bar.canonical_id, "signal_time": signal_time.isoformat(),
                                       "execution_time": bar.timestamp.isoformat(), "status": "rejected_insufficient_cash",
                                       "requested_quantity": delta})
                    else:
                        cash += -direction * notional - fee
                        positions[bar.canonical_id] = target
                        trade = {"canonical_id": bar.canonical_id, "signal_time": signal_time.isoformat(),
                                 "timestamp": bar.timestamp.isoformat(), "side": "buy" if direction > 0 else "sell",
                                 "quantity": abs(delta), "price": price, "notional": notional, "fee": fee,
                                 "slippage": slippage,
                                 "cash_after": cash}
                        trades.append(trade)
                        orders.append({**trade, "status": "filled"})
            frame = BarFrame(bar, previous, dataset.metadata_at(bar.canonical_id, bar.timestamp))
            intention = strategy.on_bar(frame)
            if intention is not None:
                if intention.canonical_id != bar.canonical_id:
                    raise ValueError("strategy returned an intention for a different canonical asset")
                if not math.isfinite(intention.quantity) or intention.quantity < 0:
                    raise ValueError("short positions are unsupported; target quantity must be non-negative")
                pending[bar.canonical_id] = (bar.timestamp, float(intention.quantity), bar.timestamp)
            history[bar.canonical_id] = previous + (bar,)
        marked = cash + sum(positions.get(asset, 0.0) * price for asset, price in last_close.items())
        equity.append({"timestamp": timestamp.isoformat(), "cash": cash, "equity": marked,
                       "positions": dict(sorted(positions.items()))})
        index = end
    if pending:
        for asset_id, (signal_time, _target, _bar_time) in sorted(pending.items()):
            orders.append({"canonical_id": asset_id, "signal_time": signal_time.isoformat(),
                           "status": "skipped_insufficient_bar"})
        if config.missing_bar_policy == "error":
            raise ValueError("insufficient bars: a pending order has no next available bar")
    return BacktestResult(tuple(trades), tuple(equity), tuple(orders), config)
