"""Read-only Helius Enhanced Transactions, DAS, and Solana RPC client."""

from __future__ import annotations

import time
from typing import Any

import requests


class SolanaProviderError(RuntimeError):
    pass


class HeliusClient:
    def __init__(self, config: dict[str, Any], api_key: str, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.api_key = api_key
        self.timeout = float(config.get("timeout_seconds", 20))
        self.max_retries = int(config.get("max_retries", 2))
        self.min_interval = 1 / float(config.get("max_requests_per_second", 2))
        self._last_request = 0.0

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        if not self.api_key:
            raise SolanaProviderError("HELIUS_API_KEY is required")
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code in (401, 403):
                    raise SolanaProviderError(f"Helius rejected request ({response.status_code})")
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.max_retries:
                        retry_after = response.headers.get("Retry-After")
                        delay = min(float(retry_after), 8.0) if retry_after else min(2 ** attempt, 8)
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and data.get("error"):
                    raise SolanaProviderError(str(data["error"]))
                return data
            except (requests.RequestException, ValueError, SolanaProviderError) as exc:
                last = exc
                if isinstance(exc, SolanaProviderError) and "rejected request" in str(exc):
                    break
                if attempt >= self.max_retries:
                    break
        raise SolanaProviderError("Helius request failed") from last

    def recent_transactions(self, address: str, *, limit: int = 20,
                            before: str | None = None) -> list[dict[str, Any]]:
        url = f"{self.config['enhanced_base_url'].rstrip('/')}/addresses/{address}/transactions"
        params = {"api-key": self.api_key, "limit": limit}
        if before is not None:
            params["before"] = before
        data = self._request("GET", url, params=params)
        return data if isinstance(data, list) else []

    def get_asset(self, mint: str) -> dict[str, Any]:
        data = self._request("POST", self.config["das_url"],
                             params={"api-key": self.api_key},
                             json={"jsonrpc": "2.0", "id": "solana-ingestion",
                                   "method": "getAsset", "params": {
                                       "id": mint, "displayOptions": {"showFungible": True}}})
        return data.get("result", {}) if isinstance(data, dict) else {}

    def largest_accounts(self, mint: str) -> list[dict[str, Any]]:
        data = self._request("POST", self.config["rpc_url"],
                             params={"api-key": self.api_key},
                             json={"jsonrpc": "2.0", "id": "solana-ingestion",
                                   "method": "getTokenLargestAccounts", "params": [mint]})
        result = data.get("result", {}) if isinstance(data, dict) else {}
        value = result.get("value", []) if isinstance(result, dict) else []
        return value if isinstance(value, list) else []
