"""Provider-neutral contracts consumed by shared EVM ingestion."""

from __future__ import annotations

from typing import Protocol

from .models import Capability, EnrichmentResult


class EVMEnrichmentProvider(Protocol):
    name: str

    def is_contract_verified(self, address: str) -> Capability: ...
    def get_top_holders(self, address: str) -> Capability: ...
    def get_deployer_address(self, address: str) -> Capability: ...

    def enrich(self, address: str) -> EnrichmentResult: ...
