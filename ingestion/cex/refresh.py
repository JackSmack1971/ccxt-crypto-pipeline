"""Refresh configured CEX candles and collect a complete ticker snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from storage.db import connect, insert_ohlcv_batch, log_run_end, log_run_start, read_assets, safe_error_message

from .common import call_with_backoff, create_exchange, load_config, timeframe_milliseconds


def refresh_exchange(exchange_id: str, *, config: dict[str, Any], db_path: str) -> int:
    exchange = create_exchange(exchange_id)
    retries = int(config.get("max_retries", 3))
    backoff = float(config.get("backoff_seconds", 1))
    run_id = log_run_start(f"cex_refresh:{exchange_id}", db_path)
    rows_written = 0
    try:
        symbols = [a["symbol_or_contract"] for a in read_assets(db_path)
                   if a["source_type"] == "cex" and a["chain_or_exchange"] == exchange_id]
        # This deliberately requests the exchange-wide snapshot as required by the refresh contract.
        tickers = call_with_backoff(exchange.fetch_tickers, retries=retries, backoff_seconds=backoff)
        for timeframe in config.get("timeframes", []):
            timeframe_ms = timeframe_milliseconds(exchange, timeframe)
            for symbol in symbols:
                connection = connect(db_path)
                try:
                    checkpoint = connection.execute(
                        "SELECT MAX(timestamp) FROM ohlcv WHERE canonical_id = ? AND timeframe = ?",
                        [f"{exchange_id}:{symbol}", timeframe],
                    ).fetchone()[0]
                finally:
                    connection.close()
                since = int(checkpoint.replace(tzinfo=timezone.utc).timestamp() * 1000) + timeframe_ms \
                    if checkpoint is not None else None
                candles = call_with_backoff(
                    lambda symbol=symbol, since=since: exchange.fetch_ohlcv(symbol, timeframe, since),
                    retries=retries, backoff_seconds=backoff,
                )
                rows = [{"canonical_id": f"{exchange_id}:{symbol}",
                         "timestamp": datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc),
                         "open": c[1], "high": c[2], "low": c[3], "close": c[4],
                         "volume": c[5], "timeframe": timeframe, "source": exchange_id}
                        for c in candles if len(c) >= 6 and c[0] is not None]
                rows_written += insert_ohlcv_batch(rows, db_path, parquet_dir=config.get("parquet_path"))
        # Keep the snapshot observable even though Goal 1 has no ticker table yet.
        _ = tickers
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
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/cex.yaml")
    parser.add_argument("--db-path")
    args = parser.parse_args()
    config = load_config(args.config)
    for exchange_id in config.get("exchanges", []):
        refresh_exchange(exchange_id, config=config, db_path=args.db_path or config["database_path"])


if __name__ == "__main__":
    main()
