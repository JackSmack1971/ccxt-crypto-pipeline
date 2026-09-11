"""Resumable, since-paginated historical CEX OHLCV ingestion."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

from storage.db import connect, insert_ohlcv_batch, log_run_end, log_run_start, safe_error_message, upsert_asset

from .common import (call_with_backoff, canonical_id, contract_address, create_exchange,
                     load_config, timeframe_milliseconds)


def _parse_since(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def backfill_symbol(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    since_ms: int,
    *,
    config: dict[str, Any],
    db_path: str,
    parquet_path: str | None = None,
) -> int:
    exchange = create_exchange(exchange_id)
    retries = int(config.get("max_retries", 3))
    backoff = float(config.get("backoff_seconds", 1))
    limit = int(config.get("ohlcv_limit", 720))
    run_id = log_run_start(f"cex_backfill:{exchange_id}:{symbol}:{timeframe}", db_path)
    rows_written = 0
    try:
        call_with_backoff(exchange.load_markets, retries=retries, backoff_seconds=backoff)
        market = exchange.markets.get(symbol)
        if not market or not market.get("spot"):
            raise ValueError(f"symbol is not a configured spot market: {exchange_id} {symbol}")

        canonical = canonical_id(exchange_id, symbol)
        now = datetime.now(timezone.utc)
        upsert_asset({"canonical_id": canonical, "source_type": "cex",
                      "chain_or_exchange": exchange_id, "symbol_or_contract": symbol,
                      "contract_address": contract_address(market),
                      "first_seen": now}, db_path)
        timeframe_ms = timeframe_milliseconds(exchange, timeframe)
        connection = connect(db_path)
        try:
            checkpoint = connection.execute(
                "SELECT MAX(timestamp) FROM ohlcv WHERE canonical_id = ? AND timeframe = ?",
                [canonical, timeframe],
            ).fetchone()[0]
        finally:
            connection.close()
        if checkpoint is not None:
            checkpoint_ms = int(checkpoint.replace(tzinfo=timezone.utc).timestamp() * 1000)
            since_ms = max(since_ms, checkpoint_ms + timeframe_ms)

        while True:
            candles = call_with_backoff(
                lambda: exchange.fetch_ohlcv(symbol, timeframe, since_ms, limit),
                retries=retries,
                backoff_seconds=backoff,
            )
            if not candles:
                break
            rows = []
            for candle in candles:
                if len(candle) < 6 or candle[0] is None:
                    continue
                rows.append({"canonical_id": canonical,
                             "timestamp": datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc),
                             "open": candle[1], "high": candle[2], "low": candle[3],
                             "close": candle[4], "volume": candle[5],
                             "timeframe": timeframe, "source": exchange_id})
            if rows:
                rows_written += insert_ohlcv_batch(rows, db_path, parquet_dir=parquet_path)
            latest = max(candle[0] for candle in candles if candle and candle[0] is not None)
            next_since = latest + timeframe_ms
            if next_since <= since_ms or len(candles) < limit:
                break
            since_ms = next_since
        log_run_end(run_id, "success", db_path, rows_written=rows_written)
        return rows_written
    except Exception as exc:
        log_run_end(run_id, "failed", db_path, rows_written=rows_written, error_message=safe_error_message(exc))
        raise
    finally:
        close = getattr(exchange, "close", None)
        if close is not None:
            close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--since", help="ISO date or timestamp; defaults to configured lookback")
    parser.add_argument("--config", default="config/cex.yaml")
    parser.add_argument("--db-path")
    args = parser.parse_args()
    config = load_config(args.config)
    since_ms = (_parse_since(args.since) if args.since else
                int((datetime.now(timezone.utc).timestamp() -
                     float(config.get("lookback_days", 365)) * 86400) * 1000))
    backfill_symbol(args.exchange, args.symbol, args.timeframe, since_ms,
                    config=config, db_path=args.db_path or config["database_path"],
                    parquet_path=config.get("parquet_path"))


if __name__ == "__main__":
    main()
