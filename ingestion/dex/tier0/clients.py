"""Read-only clients and conservative normalizers for Tier 0 providers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from .throttle import ProviderThrottles, RateLimiter


class ProviderError(RuntimeError):
    pass


def _get(session: requests.Session, url: str, *, limiter: RateLimiter, timeout: float,
         retries: int = 2) -> Any:
    last_error = None
    for attempt in range(retries + 1):
        limiter.wait()
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
                if attempt < retries:
                    time_to_wait = min(max(retry_after, 0.0), 30.0)
                    import time
                    time.sleep(time_to_wait)
                    continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                import time
                time.sleep(min(2 ** attempt, 8))
    raise ProviderError(f"request failed: {type(last_error).__name__}") from last_error


def _items(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if isinstance(body, dict):
        for key in ("data", "pairs", "tokens"):
            value = body.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


class DexScreenerClient:
    def __init__(self, *, session=None, throttles=None, base_url="https://api.dexscreener.com",
                 timeout=20):
        self.session = session or requests.Session()
        self.throttles = throttles or ProviderThrottles()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def latest_token_profiles(self):
        return _items(_get(self.session, f"{self.base_url}/token-profiles/latest/v1",
                            limiter=self.throttles.dexscreener_profiles, timeout=self.timeout))

    def latest_boosts(self):
        return _items(_get(self.session, f"{self.base_url}/token-boosts/latest/v1",
                            limiter=self.throttles.dexscreener_profiles, timeout=self.timeout))

    def pairs_for_token(self, chain: str, address: str):
        return _items(_get(self.session, f"{self.base_url}/token-pairs/v1/{chain}/{address}",
                           limiter=self.throttles.dexscreener_pairs, timeout=self.timeout))

    def latest_boosted_pairs(self):
        """Resolve the latest promoted token signals to their current pairs."""
        pairs = []
        for signal in self.latest_boosts():
            chain = signal.get("chainId")
            address = signal.get("tokenAddress")
            if chain and address:
                pairs.extend(self.pairs_for_token(chain, address))
        return pairs


class GeckoTerminalClient:
    def __init__(self, *, session=None, throttles=None,
                 base_url="https://api.geckoterminal.com/api/v2", timeout=20):
        self.session = session or requests.Session()
        self.throttles = throttles or ProviderThrottles()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _pools(self, network: str, kind: str):
        body = _get(self.session, f"{self.base_url}/networks/{network}/{kind}",
                    limiter=self.throttles.geckoterminal, timeout=self.timeout)
        included = body.get("included", []) if isinstance(body, dict) else []
        tokens = {item.get("id"): item.get("attributes", {}) for item in included
                  if isinstance(item, dict)}
        return [normalize_pool(item, network, tokens) for item in _items(body)]

    def new_pools(self, network: str):
        return self._pools(network, "new_pools")

    def trending_pools(self, network: str):
        return self._pools(network, "trending_pools")


class DefiLlamaClient:
    def __init__(self, *, session=None, throttles=None, base_url="https://api.llama.fi", timeout=20):
        self.session = session or requests.Session()
        self.throttles = throttles or ProviderThrottles()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chain_tvl(self, chain: str):
        body = _get(self.session, f"{self.base_url}/v2/historicalChainTvl/{chain}",
                    limiter=self.throttles.defillama, timeout=self.timeout)
        return {"chain": chain, "historical_tvl": body}

    def protocols(self):
        return _get(self.session, f"{self.base_url}/protocols",
                    limiter=self.throttles.defillama, timeout=self.timeout)


def _token_address(token_id: str | None) -> str | None:
    if not token_id:
        return None
    return token_id.split("_", 1)[1] if "_" in token_id else None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, tz=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def normalize_pool(item: dict[str, Any], network: str, tokens: dict[str, dict[str, Any]] | None = None):
    attributes = item.get("attributes", item)
    relationships = item.get("relationships", {})
    token_data = {}
    for key in ("base_token", "quote_token"):
        relationship = relationships.get(key, {})
        data = relationship.get("data", {}) if isinstance(relationship, dict) else {}
        token_data[key] = (data.get("id") if isinstance(data, dict) else None)
    tokens = tokens or {}
    pool_address = attributes.get("address") or item.get("id", "").split("_", 1)[-1]
    return {
        "network": network,
        "pool_address": pool_address,
        "name": attributes.get("name"),
        "dex_id": attributes.get("dex_id"),
        "created_at": _timestamp(attributes.get("pool_created_at") or attributes.get("created_at")),
        "base_token_address": _token_address(token_data["base_token"]),
        "quote_token_address": _token_address(token_data["quote_token"]),
        "base_token": tokens.get(token_data["base_token"], {}),
        "quote_token": tokens.get(token_data["quote_token"], {}),
        "reserve_usd": attributes.get("reserve_in_usd"),
        "raw": item,
    }
