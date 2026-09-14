"""Shared EVM event-to-storage flow; it only consumes normalized adapters."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from storage.db import (advance_ingestion_cursor, get_ingestion_cursor, insert_event, log_run_end,
                        log_run_start, safe_error_message, upsert_asset, upsert_asset_relationship,
                        upsert_metadata)

from .config import ROOT, load_chain, load_evm_config
from .models import CapabilityStatus
from .providers import build_provider
from .risk import risk_flags
from .risk import HoneypotRiskProvider
from .rpc import EVMRPCClient, decode_created_market, rpc_url_from_env


def enrich_asset(chain: str, chain_id: int, address: str, provider, risk_provider, *, db_path: str,
                 now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    result = provider.enrich(address)
    flags = {
        "risk": risk_flags(risk_provider, address, chain_id),
        "enrichment": {
            "provider": result.provider,
            "contract_verified": {"status": result.contract_verified.status.value,
                                   "reason": result.contract_verified.reason},
            "top_holders": {"status": result.top_holders.status.value,
                             "reason": result.top_holders.reason},
            "deployer_address": {"status": result.deployer_address.status.value,
                                  "reason": result.deployer_address.reason},
        },
    }
    upsert_asset({"canonical_id": f"{chain}:{address}", "source_type": "dex",
                  "chain_or_exchange": chain, "symbol_or_contract": address, "first_seen": now}, db_path)
    upsert_metadata({"canonical_id": f"{chain}:{address}", "holder_count": result.holder_count,
                     "contract_verified": result.contract_verified.value if result.contract_verified.status is CapabilityStatus.AVAILABLE else None,
                     "deployer_address": result.deployer_address.value if result.deployer_address.status is CapabilityStatus.AVAILABLE else None,
                     "risk_flags_json": flags, "last_updated": now}, db_path)


def observe_once(chain_config: dict[str, Any], rpc: EVMRPCClient, provider, risk_provider, *,
                 db_path: str, from_block: int, to_block: int, run_id: str | None = None,
                 cursor_source: str | None = None) -> int:
    run_id = run_id or log_run_start(f"evm_listener:{chain_config['name']}", db_path)
    written = 0
    try:
        cursor = (get_ingestion_cursor(cursor_source, chain_config["name"], db_path)
                  if cursor_source is not None else None)
        previous = cursor["position"] if cursor else None
        if previous is not None and from_block > previous + 1:
            raise ValueError(
                f"skipped block range for {cursor_source}/{chain_config['name']}: "
                f"expected at most {previous + 1}, got {from_block}"
            )
        if from_block > to_block:
            raise ValueError(f"invalid block range: {from_block} > {to_block}")
        logs = rpc.get_factory_logs(chain_config.get("factories", []), from_block, to_block)
        for log in logs:
            decoded = decode_created_market(log)
            if decoded:
                address = decoded["market_address"]
                now = log.get("timestamp") or datetime.now(timezone.utc)
                upsert_asset({"canonical_id": f"{chain_config['name']}:{address}", "source_type": "dex",
                              "chain_or_exchange": chain_config["name"], "symbol_or_contract": address,
                              "first_seen": now}, db_path)
                for index, token_address in enumerate(decoded["constituents"]):
                    if token_address is None:
                        continue
                    enrich_asset(chain_config["name"], int(chain_config["chain_id"]), token_address,
                                 provider, risk_provider, db_path=db_path, now=now)
                    upsert_asset_relationship({"market_canonical_id": f"{chain_config['name']}:{address}",
                                               "asset_canonical_id": f"{chain_config['name']}:{token_address}",
                                               "relationship_type": f"constituent_{index}",
                                               "venue": str(log.get("protocol") or "unknown"),
                                               "observed_at": now, "source": "evm_rpc",
                                               "evidence_json": {"log": log}}, db_path)
                if log.get("timestamp") is not None:
                    insert_event({"canonical_id": f"{chain_config['name']}:{address}",
                                  "event_type": "new_pool_detected", "timestamp": log["timestamp"],
                                  "payload_json": {"protocol": log.get("protocol"), "log": log},
                                  "source": "evm_rpc"}, db_path)
                written += 1
        if cursor_source is not None:
            advance_ingestion_cursor(cursor_source, chain_config["name"],
                                     max(to_block, previous if previous is not None else to_block), db_path,
                                     run_id=run_id, expected_previous=previous)
        log_run_end(run_id, "success", db_path, rows_written=written)
        return written
    except Exception as exc:
        log_run_end(run_id, "failed", db_path, rows_written=written, error_message=safe_error_message(exc))
        raise


def run_once(chain: str, *, db_path: str, from_block: int | None = None,
             to_block: int | None = None, lookback_blocks: int = 1000, root=ROOT) -> int:
    """Run one configured chain observation without coupling RPC and explorers."""
    chain_config = load_chain(chain, root)
    run_id = log_run_start(f"evm_listener:{chain}", db_path)
    observation_started = False
    try:
        provider_config = load_evm_config(root)
        rpc = EVMRPCClient(rpc_url_from_env(chain_config["rpc_env"]))
        end = to_block if to_block is not None else rpc.latest_block()
        cursor = get_ingestion_cursor("evm_rpc", chain, db_path)
        start = from_block if from_block is not None else (
            cursor["position"] + 1 if cursor is not None else max(0, end - lookback_blocks)
        )
        if from_block is None and cursor is not None and start > end:
            log_run_end(run_id, "success", db_path, rows_written=0)
            return 0
        provider = build_provider(chain, int(chain_config["chain_id"]), provider_config)
        risk = HoneypotRiskProvider(provider_config["risk"])
        observation_started = True
        return observe_once(chain_config, rpc, provider, risk, db_path=db_path,
                            from_block=start, to_block=end, run_id=run_id,
                            cursor_source="evm_rpc")
    except Exception as exc:
        if not observation_started:
            log_run_end(run_id, "failed", db_path, error_message=safe_error_message(exc))
        raise
