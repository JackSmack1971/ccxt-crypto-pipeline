"""Shared configuration, ccxt construction, and retry helpers for CEX jobs."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import ccxt
import yaml


DEFAULT_CONFIG_PATH = Path("config/cex.yaml")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError("CEX configuration must be a mapping")
    return config


def create_exchange(exchange_id: str):
    try:
        exchange_class = getattr(ccxt, exchange_id)
    except AttributeError as exc:
        raise ValueError(f"unsupported ccxt exchange: {exchange_id}") from exc
    return exchange_class({"enableRateLimit": True})


def call_with_backoff(
    operation: Callable[[], Any],
    *,
    retries: int,
    backoff_seconds: float,
) -> Any:
    """Retry only transient ccxt failures, with bounded exponential backoff."""
    transient = (
        ccxt.NetworkError,
        ccxt.RequestTimeout,
        ccxt.ExchangeNotAvailable,
        ccxt.DDoSProtection,
        ccxt.RateLimitExceeded,
    )
    for attempt in range(retries + 1):
        try:
            return operation()
        except transient:
            if attempt >= retries:
                raise
            time.sleep(backoff_seconds * (2**attempt))


def timeframe_milliseconds(exchange, timeframe: str) -> int:
    milliseconds = exchange.parse_timeframe(timeframe) * 1000
    if milliseconds <= 0:
        raise ValueError(f"invalid timeframe: {timeframe}")
    return milliseconds


def canonical_id(exchange_id: str, symbol: str) -> str:
    return f"{exchange_id}:{symbol}"


def contract_address(market: dict[str, Any]) -> str | None:
    """Return an exchange-published base-token address when one is present.

    CCXT has no unified contract-address field, so adapters may expose it in
    their raw market metadata under one of these documented names.
    """
    info = market.get("info") if isinstance(market, dict) else None
    candidates = [market, info]
    if isinstance(info, dict):
        candidates.extend(info.get(key) for key in ("base", "baseAsset", "token")
                          if isinstance(info.get(key), dict))
    keys = ("contractAddress", "contract_address", "baseContractAddress", "base_contract_address",
            "tokenAddress", "token_address")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in keys:
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
