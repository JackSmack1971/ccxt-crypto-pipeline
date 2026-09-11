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


def decode_created_asset(log: dict[str, Any]) -> str | None:
    topics = log.get("topics") or []
    data = str(log.get("data", ""))[2:]
    if len(topics) >= 3 and str(topics[0]).lower() == PAIR_CREATED_TOPIC:
        return "0x" + data[24:64] if len(data) >= 64 else None
    if len(topics) >= 3 and str(topics[0]).lower() == POOL_CREATED_TOPIC:
        return "0x" + data[-40:] if len(data) >= 40 else None
    return None


def rpc_url_from_env(env_name: str) -> str:
    return os.getenv(env_name, "")
