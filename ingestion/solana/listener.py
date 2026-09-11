"""Solana launch discovery and normalized persistence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Iterable

from storage.db import (insert_event, log_run_end, log_run_start, safe_error_message, upsert_asset,
                        upsert_asset_relationship, upsert_metadata)

from .config import ROOT, load_config
from .helius import HeliusClient

_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def is_solana_address(value: str) -> bool:
    """Validate the shape of a Solana public key without adding a dependency."""
    if not isinstance(value, str) or not value or any(char not in _BASE58 for char in value):
        return False
    number = 0
    for char in value:
        number = number * 58 + _BASE58.index(char)
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return len(raw) + len(value) - len(value.lstrip("1")) == 32


def _find_values(value: Any, names: set[str]) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in names and isinstance(child, str) and child:
                yield child
            yield from _find_values(child, names)
    elif isinstance(value, list):
        for child in value:
            yield from _find_values(child, names)


def extract_mints(transaction: dict[str, Any]) -> list[str]:
    names = {"mint", "tokenmint", "token_mint", "token1mint", "token2mint"}
    return list(dict.fromkeys(mint for mint in _find_values(transaction, names)
                             if is_solana_address(mint)))


def extract_pool_addresses(transaction: dict[str, Any]) -> list[str]:
    names = {"pool", "pooladdress", "pool_address", "pair", "pairaddress", "pair_address"}
    return list(dict.fromkeys(address for address in _find_values(transaction, names)
                             if is_solana_address(address)))


def _event_type(transaction: dict[str, Any], configured_types: list[str]) -> str | None:
    tx_type = str(transaction.get("type", ""))
    if tx_type in configured_types:
        return "new_pool_detected" if tx_type == "CREATE_POOL" else "token_mint_detected"
    return None


def persist_launch(mint: str, transaction: dict[str, Any], client: HeliusClient, *, db_path: str,
                   now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    asset = client.get_asset(mint)
    holders = client.largest_accounts(mint)
    canonical_id = f"solana:{mint}"
    token_info = asset.get("token_info", {}) if isinstance(asset, dict) else {}
    metadata = asset.get("content", {}).get("metadata", {}) if isinstance(asset, dict) else {}
    upsert_asset({"canonical_id": canonical_id, "source_type": "dex",
                  "chain_or_exchange": "solana", "symbol_or_contract": mint, "first_seen": now}, db_path)
    upsert_metadata({"canonical_id": canonical_id, "holder_count": len(holders),
                     "lp_locked": None, "contract_verified": None,
                     "deployer_address": transaction.get("feePayer"),
                     "risk_flags_json": {"provider": "helius", "risk_screen": "UNSUPPORTED",
                                         "token_metadata": metadata, "token_info": token_info,
                                         "top_holders": holders}, "last_updated": now}, db_path)
    return 1


def run_once(*, db_path: str, config: dict[str, Any] | None = None, client: HeliusClient | None = None,
             now: datetime | None = None) -> int:
    config = config or load_config()
    client = client or HeliusClient(config)
    run_id = log_run_start("solana_listener", db_path)
    written = 0
    try:
        programs = config.get("programs", {})
        limit = int(config.get("discovery", {}).get("limit", 20))
        types = config.get("discovery", {}).get("transaction_types", ["TOKEN_MINT", "CREATE_POOL"])
        for program_name, address in programs.items():
            for tx in client.recent_transactions(address, limit=limit):
                event_type = _event_type(tx, types)
                mints = extract_mints(tx)
                if not event_type or not mints:
                    continue
                if not tx.get("timestamp") and now is None:
                    continue
                timestamp = datetime.fromtimestamp(tx["timestamp"], timezone.utc) if tx.get("timestamp") else now
                pool_addresses = extract_pool_addresses(tx) if event_type == "new_pool_detected" else []
                # A pool relationship is persisted only when its two-sided
                # identity can be represented without guessing from symbols or
                # unrelated transaction accounts.
                if event_type == "new_pool_detected" and (len(pool_addresses) != 1 or len(mints) != 2):
                    continue
                for mint in mints:
                    canonical_id = f"solana:{mint}"
                    event_identity = f"solana:{pool_addresses[0]}" if len(pool_addresses) == 1 else canonical_id
                    if len(pool_addresses) == 1:
                        upsert_asset({"canonical_id": event_identity, "source_type": "dex",
                                      "chain_or_exchange": "solana", "symbol_or_contract": pool_addresses[0],
                                      "first_seen": timestamp}, db_path)
                    insert_event({"canonical_id": event_identity, "event_type": event_type,
                                  "timestamp": timestamp, "payload_json": {"program": program_name, "transaction": tx},
                                  "source": "helius"}, db_path)
                    written += persist_launch(mint, tx, client, db_path=db_path, now=timestamp)
                    if len(pool_addresses) == 1:
                        upsert_asset_relationship({"market_canonical_id": event_identity,
                                                   "asset_canonical_id": canonical_id,
                                                   "relationship_type": f"constituent_{mints.index(mint)}",
                                                   "venue": program_name, "observed_at": timestamp,
                                                   "source": "helius", "evidence_json": {"transaction": tx}}, db_path)
        log_run_end(run_id, "success", db_path, rows_written=written)
        return written
    except Exception as exc:
        log_run_end(run_id, "failed", db_path, rows_written=written, error_message=safe_error_message(exc))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one Solana Tier 2 discovery/enrichment pass")
    parser.add_argument("--db", default="storage/pipeline.duckdb", help="DuckDB path")
    args = parser.parse_args()
    print(run_once(db_path=args.db))
