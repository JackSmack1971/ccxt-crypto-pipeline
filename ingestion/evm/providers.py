"""Explorer/indexer adapters. RPC observation is intentionally elsewhere."""

from __future__ import annotations

import os
import time
from typing import Any

from storage.db import safe_error_message

import requests

from .models import Capability, CapabilityStatus, EnrichmentResult


class ProviderError(RuntimeError):
    pass


def _available(value: Any) -> Capability:
    return Capability(CapabilityStatus.AVAILABLE, value=value)


def _unsupported(reason: str) -> Capability:
    return Capability(CapabilityStatus.UNSUPPORTED, reason=reason)


class HTTPProvider:
    name = "provider"

    def __init__(self, config: dict[str, Any], session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.timeout = float(config.get("timeout_seconds", 20))
        self.max_retries = int(config.get("max_retries", 2))
        self.min_interval = float(config.get("min_interval_seconds", 0))
        self._last_request = 0.0

    def _get(self, url: str, *, params: dict[str, Any] | None = None, headers=None) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if self.min_interval:
                    elapsed = time.monotonic() - self._last_request
                    if elapsed < self.min_interval:
                        time.sleep(self.min_interval - elapsed)
                self._last_request = time.monotonic()
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                if response.status_code in (401, 403):
                    raise ProviderError(f"{self.name} rejected request ({response.status_code})")
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.max_retries:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            delay = min(float(retry_after), 8.0) if retry_after else min(2 ** attempt, 8)
                        except ValueError:
                            delay = min(2 ** attempt, 8)
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
        raise ProviderError(f"{self.name} request failed") from last_error

    @staticmethod
    def _result(data: Any) -> Any:
        if not isinstance(data, dict):
            raise ProviderError("provider response is not an object")
        if str(data.get("status", "1")) == "0":
            raise ProviderError(str(data.get("message", "provider returned an error")))
        return data.get("result", data.get("items", data))


class EtherscanV2Provider(HTTPProvider):
    name = "etherscan_v2"

    def __init__(self, chain_id: int, config: dict[str, Any], session=None):
        super().__init__(config, session)
        self.chain_id = chain_id
        self.api_key = os.getenv(config.get("api_key_env", "ETHERSCAN_API_KEY"), "")

    def _call(self, action: str, address: str) -> Any:
        return self._result(self._get(self.config["base_url"], params={
            "apikey": self.api_key, "chainid": str(self.chain_id), "module": "contract",
            "action": action, "address": address,
        }))

    def is_contract_verified(self, address: str) -> Capability:
        try:
            rows = self._call("getsourcecode", address)
            row = rows[0] if isinstance(rows, list) and rows else rows
            verified = bool(isinstance(row, dict) and row.get("SourceCode"))
            return _available(verified)
        except ProviderError as exc:
            return Capability(CapabilityStatus.UNAVAILABLE, reason=safe_error_message(exc))

    def get_top_holders(self, address: str) -> Capability:
        try:
            rows = self._result(self._get(self.config["base_url"], params={
                "apikey": self.api_key, "chainid": str(self.chain_id), "module": "token",
                "action": "tokenholderlist", "contractaddress": address, "page": 1, "offset": 100,
            }))
            if not isinstance(rows, list):
                raise ProviderError("holder response is not a list")
            return _available(rows)
        except ProviderError as exc:
            return Capability(CapabilityStatus.UNAVAILABLE, reason=safe_error_message(exc))

    def get_deployer_address(self, address: str) -> Capability:
        try:
            rows = self._result(self._get(self.config["base_url"], params={
                "apikey": self.api_key, "chainid": str(self.chain_id), "module": "contract",
                "action": "getcontractcreation", "contractaddresses": address,
            }))
            row = rows[0] if isinstance(rows, list) and rows else None
            deployer = row.get("contractCreator") if isinstance(row, dict) else None
            return _available(deployer) if deployer else _unsupported("provider returned no deployer")
        except ProviderError as exc:
            return Capability(CapabilityStatus.UNAVAILABLE, reason=safe_error_message(exc))

    def enrich(self, address: str) -> EnrichmentResult:
        return EnrichmentResult(self.name, self.is_contract_verified(address),
                                self.get_top_holders(address), self.get_deployer_address(address))


class RoutescanProvider(HTTPProvider):
    name = "routescan"

    def __init__(self, chain_id: int, config: dict[str, Any], session=None):
        super().__init__(config, session)
        self.chain_id = chain_id
        self.api_key = os.getenv(config.get("api_key_env", "ROUTESCAN_API_KEY"), "")
        if not self.api_key:
            if not config.get("allow_keyless", False):
                self.keyless_enabled = False
            else:
                self.keyless_enabled = True
                self.min_interval = max(self.min_interval, 1 / float(config.get("keyless_requests_per_second", 2)))
        else:
            self.keyless_enabled = True
            self.min_interval = max(self.min_interval, 1 / float(config.get("keyed_requests_per_second", 5)))

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.api_key} if self.api_key else {}

    def _url(self, suffix: str) -> str:
        return f"{self.config['base_url'].rstrip('/')}/{self.chain_id}/{suffix.lstrip('/')}"

    def is_contract_verified(self, address: str) -> Capability:
        return _unsupported("Routescan contract verification is not part of this adapter's free contract")

    def get_top_holders(self, address: str) -> Capability:
        if not self.keyless_enabled:
            return _unsupported("Routescan keyless access is not enabled and no API key is configured")
        try:
            data = self._get(self._url(f"erc20/{address}/holders"),
                             params={"limit": 100}, headers=self._headers())
            rows = data.get("items", []) if isinstance(data, dict) else []
            return _available(rows) if isinstance(rows, list) else _unsupported("invalid holders response")
        except ProviderError as exc:
            return Capability(CapabilityStatus.UNAVAILABLE, reason=safe_error_message(exc))

    def get_deployer_address(self, address: str) -> Capability:
        return _unsupported("Routescan deployer capability requires a configured indexed endpoint")

    def enrich(self, address: str) -> EnrichmentResult:
        return EnrichmentResult(self.name, self.is_contract_verified(address),
                                self.get_top_holders(address), self.get_deployer_address(address))


class MegaNodeProvider(HTTPProvider):
    name = "bsctrace_meganode"

    def is_contract_verified(self, address: str) -> Capability:
        return _unsupported("MegaNode endpoint contract is not configured")

    def get_top_holders(self, address: str) -> Capability:
        return _unsupported("MegaNode endpoint contract is not configured")

    def get_deployer_address(self, address: str) -> Capability:
        return _unsupported("MegaNode endpoint contract is not configured")

    def enrich(self, address: str) -> EnrichmentResult:
        return EnrichmentResult(self.name, self.is_contract_verified(address),
                                self.get_top_holders(address), self.get_deployer_address(address))


def build_provider(chain: str, chain_id: int, config: dict[str, Any], session=None) -> EtherscanV2Provider | RoutescanProvider | MegaNodeProvider:
    name = config.get("providers", {}).get(chain)
    provider_config = config.get(name, {})
    if name == "etherscan_v2":
        return EtherscanV2Provider(chain_id, provider_config, session)
    if name == "routescan":
        return RoutescanProvider(chain_id, provider_config, session)
    if name == "bsctrace_meganode":
        return MegaNodeProvider(provider_config, session)
    raise ValueError(f"no EVM provider configured for {chain}")
