"""Free, keyless honeypot screening adapter."""

from __future__ import annotations

from typing import Any

from .models import CapabilityStatus
from storage.db import safe_error_message
from .providers import HTTPProvider


class HoneypotRiskProvider(HTTPProvider):
    name = "honeypot_is"

    def screen(self, address: str, chain_id: int) -> dict[str, Any]:
        data = self._get(self.config["base_url"], params={"address": address, "chainID": chain_id})
        summary = data.get("summary", {}) if isinstance(data, dict) else {}
        return {"provider": self.name, "chain_id": chain_id, "risk": summary}


def risk_flags(provider: HoneypotRiskProvider, address: str, chain_id: int) -> dict[str, Any]:
    try:
        return provider.screen(address, chain_id)
    except Exception as exc:  # risk evidence must not abort unrelated observation
        return {"provider": provider.name, "status": CapabilityStatus.UNAVAILABLE.value, "reason": safe_error_message(exc)}
