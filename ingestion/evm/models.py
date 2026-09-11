"""Shared normalized EVM values; provider-specific response shapes stop here."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class Capability:
    status: CapabilityStatus
    value: Any = None
    reason: str | None = None


@dataclass(frozen=True)
class EnrichmentResult:
    provider: str
    contract_verified: Capability
    top_holders: Capability
    deployer_address: Capability
    risk_flags: dict[str, Any] = field(default_factory=dict)

    @property
    def holder_count(self) -> int | None:
        if self.top_holders.status is not CapabilityStatus.AVAILABLE:
            return None
        value = self.top_holders.value
        return len(value) if isinstance(value, list) else (int(value) if value is not None else None)
