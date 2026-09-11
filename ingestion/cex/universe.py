"""Discover configured exchanges' spot markets above the volume threshold."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from storage.db import log_run_end, log_run_start, safe_error_message, upsert_asset

from .common import call_with_backoff, canonical_id, contract_address, create_exchange, load_config


def discover_universe(config: dict[str, Any], *, db_path: str) -> list[dict[str, Any]]:
    minimum_volume = float(config.get("minimum_24h_quote_volume", 0))
    result: list[dict[str, Any]] = []
    for exchange_id in config.get("exchanges", []):
        exchange = create_exchange(exchange_id)
        retries = int(config.get("max_retries", 3))
        backoff = float(config.get("backoff_seconds", 1))
        run_id = log_run_start(f"cex_universe:{exchange_id}", db_path)
        rows_written = 0
        try:
            markets = call_with_backoff(exchange.fetch_markets, retries=retries, backoff_seconds=backoff)
            tickers = call_with_backoff(exchange.fetch_tickers, retries=retries, backoff_seconds=backoff)
            now = datetime.now(timezone.utc)
            for market in markets:
                if not market.get("spot") or not market.get("symbol"):
                    continue
                ticker = tickers.get(market["symbol"], {}) or {}
                volume = ticker.get("quoteVolume")
                if volume is None:
                    continue
                if float(volume) < minimum_volume:
                    continue
                asset = {
                    "canonical_id": canonical_id(exchange_id, market["symbol"]),
                    "source_type": "cex",
                    "chain_or_exchange": exchange_id,
                    "symbol_or_contract": market["symbol"],
                    "contract_address": contract_address(market),
                    "first_seen": now,
                }
                upsert_asset(asset, db_path)
                result.append(asset)
                rows_written += 1
            log_run_end(run_id, "success", db_path, rows_written=rows_written)
        except Exception as exc:
            log_run_end(run_id, "failed", db_path, rows_written=rows_written, error_message=safe_error_message(exc))
            raise
        finally:
            close = getattr(exchange, "close", None)
            if close is not None:
                close()
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/cex.yaml")
    parser.add_argument("--db-path")
    args = parser.parse_args()
    config = load_config(args.config)
    discover_universe(config, db_path=args.db_path or config["database_path"])


if __name__ == "__main__":
    main()
