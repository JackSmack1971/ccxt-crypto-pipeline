"""Solana launch discovery and normalized persistence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Iterable

from storage.db import (advance_ingestion_continuation, get_ingestion_continuation, insert_event,
                        log_run_end, log_run_start, safe_error_message, upsert_asset,
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


def _transactions_since(client: HeliusClient, address: str, *, checkpoint: str | None,
                        page_size: int, max_pages: int) -> tuple[list[dict[str, Any]], str | None]:
    """Page newest-to-oldest until the prior durable signature is reached."""
    before = None
    collected: list[dict[str, Any]] = []
    newest_signature = None
    for _ in range(max_pages):
        page = client.recent_transactions(address, limit=page_size, before=before)
        if not page:
            if checkpoint is not None:
                raise RuntimeError(f"Solana continuation {checkpoint!r} was not found for {address}")
            break
        signatures = [tx.get("signature") for tx in page]
        if any(not isinstance(signature, str) or not signature for signature in signatures):
            raise ValueError(f"Helius transaction page for {address} contains a missing signature")
        if newest_signature is None:
            newest_signature = signatures[0]
        if checkpoint in signatures:
            collected.extend(page[:signatures.index(checkpoint)])
            return list(reversed(collected)), newest_signature
        collected.extend(page)
        before = signatures[-1]
        if checkpoint is None:
            # The initial observation boundary is explicitly the newest provider page.
            return list(reversed(collected)), newest_signature
    if checkpoint is not None:
        raise RuntimeError(
            f"Solana continuation {checkpoint!r} was not reached within {max_pages} pages for {address}"
        )
    return list(reversed(collected)), newest_signature


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
        discovery = config.get("discovery", {})
        limit = int(discovery.get("limit", 20))
        max_pages = int(discovery.get("max_pages", 25))
        if limit <= 0 or max_pages <= 0:
            raise ValueError("Solana discovery limit and max_pages must be positive")
        types = discovery.get("transaction_types", ["TOKEN_MINT", "CREATE_POOL"])
        for program_name, address in programs.items():
            cursor = get_ingestion_continuation("helius_enhanced", address, db_path)
            checkpoint = cursor["token"] if cursor else None
            transactions, newest_signature = _transactions_since(
                client, address, checkpoint=checkpoint, page_size=limit, max_pages=max_pages
            )
            for tx in transactions:
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
            if newest_signature is not None and newest_signature != checkpoint:
                advance_ingestion_continuation(
                    "helius_enhanced", address, newest_signature, db_path,
                    updated_at=now, run_id=run_id, expected_previous=checkpoint,
                )
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
