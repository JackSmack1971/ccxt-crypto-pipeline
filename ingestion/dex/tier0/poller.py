"""Chain-agnostic Tier 0 discovery and canonical persistence."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from storage.db import insert_event, log_run_end, log_run_start, safe_error_message, upsert_asset

from .clients import GeckoTerminalClient, ProviderError


def load_config(path="config/chains.yaml") -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _asset(network: str, address: str, token: dict[str, Any], now: datetime):
    return {"canonical_id": f"{network}:{address}", "source_type": "dex",
            "chain_or_exchange": network, "symbol_or_contract": address, "first_seen": now}


def poll_network(network_config: dict[str, Any], *, db_path="storage/pipeline.duckdb",
                 gecko=None, max_pools=20, now=None) -> int:
    network = network_config["name"]
    gecko_network = network_config.get("gecko_network", network)
    gecko = gecko or GeckoTerminalClient()
    now = now or datetime.now(timezone.utc)
    written = 0
    try:
        new_pools = gecko.new_pools(gecko_network)
    except ProviderError:
        new_pools = []
    try:
        trending_pools = gecko.trending_pools(gecko_network)
    except ProviderError:
        trending_pools = []
    for event_type, pools in (("new_pool_detected", new_pools), ("trending", trending_pools)):
        for pool in pools[:max_pools]:
            address = pool.get("pool_address")
            if not address:
                continue
            canonical_id = f"{network}:{address}"
            upsert_asset(_asset(network, address, pool, now), db_path)
            insert_event({"canonical_id": canonical_id, "event_type": event_type,
                          "timestamp": pool["created_at"],
                          "payload_json": json.dumps(pool, default=str, sort_keys=True),
                          "source": "geckoterminal"}, db_path)
            written += 1
            for token_key in ("base_token_address", "quote_token_address"):
                token_address = pool.get(token_key)
                if token_address:
                    upsert_asset(_asset(network, token_address, pool.get(token_key, {}), now), db_path)
    return written


def poll(config_path="config/chains.yaml", *, db_path=None, gecko=None) -> int:
    config = load_config(config_path)
    if db_path is None:
        db_path = "storage/pipeline.duckdb"
    run_id = log_run_start("tier0_dex_poll", db_path)
    written = 0
    try:
        for network in config.get("networks", []):
            written += poll_network(network, db_path=db_path, gecko=gecko,
                                    max_pools=config.get("max_pools_per_network", 20))
    except Exception as exc:
        log_run_end(run_id, "failed", db_path, rows_written=written, error_message=safe_error_message(exc))
        raise
    log_run_end(run_id, "success", db_path, rows_written=written)
    return written


def poll_forever(config_path="config/chains.yaml", *, db_path=None, gecko=None) -> None:
    """Run the configured network poll at the configured interval."""
    config = load_config(config_path)
    interval = max(60, int(config.get("poll_interval_minutes", 20) * 60))
    while True:
        poll(config_path, db_path=db_path, gecko=gecko)
        time.sleep(interval)


if __name__ == "__main__":
    print(poll())
