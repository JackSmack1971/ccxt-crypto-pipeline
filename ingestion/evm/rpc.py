"""Chain-parameterized JSON-RPC log observation shared by all EVM chains."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

PAIR_CREATED_TOPIC = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
POOL_CREATED_TOPIC = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"


class RPCError(RuntimeError):
    pass


class EVMRPCClient:
    def __init__(self, rpc_url: str, session: requests.Session | None = None, timeout: float = 20):
        if not rpc_url:
            raise ValueError("RPC URL is required")
        self.rpc_url = rpc_url
        self.session = session or requests.Session()
        self.timeout = timeout

    def call(self, method: str, params: list[Any]) -> Any:
        response = self.session.post(self.rpc_url, json={"jsonrpc": "2.0", "id": 1,
                                                          "method": method, "params": params},
                                     timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            raise RPCError(str(body["error"]))
        return body.get("result")

    def latest_block(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def get_block(self, block_number: int) -> dict[str, Any]:
        block = self.call("eth_getBlockByNumber", [hex(block_number), False]) or {}
        if not block.get("hash") or not block.get("parentHash"):
            raise RPCError(f"missing canonical identity for block {block_number}")
        return block

    def get_factory_logs(self, factories: list[dict[str, str]], from_block: int, to_block: int) -> list[dict[str, Any]]:
        logs: list[dict[str, Any]] = []
        for factory in factories:
            result = self.call("eth_getLogs", [{"address": factory["address"],
                "fromBlock": hex(from_block), "toBlock": hex(to_block),
                "topics": [[PAIR_CREATED_TOPIC, POOL_CREATED_TOPIC]]}]) or []
            for log in result:
                normalized = {**log, "protocol": factory.get("protocol", "unknown")}
                block_number = log.get("blockNumber")
                if block_number:
                    block = self.call("eth_getBlockByNumber", [block_number, False]) or {}
                    block_timestamp = block.get("timestamp")
                    if block_timestamp:
                        normalized["timestamp"] = datetime.fromtimestamp(
                            int(block_timestamp, 16), timezone.utc
                        )
                logs.append(normalized)
        return logs


def _topic_address(value: Any) -> str | None:
    encoded = str(value).removeprefix("0x")
    return "0x" + encoded[-40:] if len(encoded) == 64 else None


def decode_created_market(log: dict[str, Any]) -> dict[str, Any] | None:
    """Decode a supported factory log into its market and two constituents."""
    topics = log.get("topics") or []
    data = str(log.get("data", ""))[2:]
    if len(topics) >= 3 and str(topics[0]).lower() in {PAIR_CREATED_TOPIC, POOL_CREATED_TOPIC}:
        market = "0x" + (data[24:64] if str(topics[0]).lower() == PAIR_CREATED_TOPIC else data[-40:])
        if len(market) != 42:
            return None
        return {"market_address": market, "constituents": (_topic_address(topics[1]), _topic_address(topics[2]))}
    return None


def decode_created_asset(log: dict[str, Any]) -> str | None:
    """Backward-compatible market-address decoder."""
    decoded = decode_created_market(log)
    return decoded["market_address"] if decoded else None


def rpc_url_from_env(env_name: str) -> str:
    return os.getenv(env_name, "")
