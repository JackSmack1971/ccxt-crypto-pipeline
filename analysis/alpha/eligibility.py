"""Chain/source research-eligibility gating from offline provider quality facts.

Cohort membership (which launches were observed) and analysis eligibility
(liquidity/coverage at `t0`) are decided per cohort row in `cohort.py`. This
module adds a third, coarser tier that is decided *before* cohort
construction: whether a chain's provider observation history is healthy
enough for any of its rows to be treated as research-eligible at all.

This module is a pure function over already-materialized quality facts. It
does not read `storage/db.py` or any provider/network boundary itself --
the caller is responsible for fetching `storage.db.provider_quality_summary`
rows and declaring which `(source, scope)` keys back each chain, keeping the
same offline/local-only boundary as the rest of `analysis/alpha`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class EligibilityPolicy:
    """Configurable thresholds applied to `storage.db.provider_quality_summary` rows."""

    min_completeness_ratio: float = 0.9
    max_observed_gap_seconds: float | None = None
    max_expected_interval_multiple: float = 3.0

    def __post_init__(self):
        if not 0 < self.min_completeness_ratio <= 1:
            raise ValueError("min_completeness_ratio must be in (0, 1]")
        if self.max_observed_gap_seconds is not None and self.max_observed_gap_seconds <= 0:
            raise ValueError("max_observed_gap_seconds must be positive when set")
        if self.max_expected_interval_multiple <= 0:
            raise ValueError("max_expected_interval_multiple must be positive")


@dataclass(frozen=True)
class ChainEligibility:
    chain: str
    eligible: bool
    reason: str | None
    quality: tuple[dict[str, Any], ...]


def evaluate_chain_eligibility(
    quality_rows: Sequence[Mapping[str, Any]],
    chain_scopes: Mapping[str, Sequence[tuple[str, str]]],
    *, policy: EligibilityPolicy = EligibilityPolicy(),
) -> dict[str, ChainEligibility]:
    """Decide, per configured chain, whether it is eligible for cohort construction.

    `chain_scopes` maps a chain name (matching `CohortConfig.chains`) to the
    `provider_observation_log` `(source, scope)` keys that back it, e.g.
    `{"ethereum": [("evm_rpc", "ethereum")],
      "solana": [("helius_enhanced", addr) for addr in program_addresses]}`.

    A chain declared with no scopes, or whose scopes have no recorded
    observations, is explicitly unobserved rather than silently treated as
    healthy: cohort construction MUST NOT infer eligibility from missing
    provider evidence.
    """
    index = {(row["source"], row["scope"]): row for row in quality_rows}
    results: dict[str, ChainEligibility] = {}
    for chain, scopes in chain_scopes.items():
        if not scopes:
            results[chain] = ChainEligibility(chain, False, "NO_CONFIGURED_SCOPE", ())
            continue
        rows = tuple(index[key] for key in scopes if key in index)
        if not rows:
            results[chain] = ChainEligibility(chain, False, "NO_PROVIDER_OBSERVATIONS", ())
            continue
        reason = None
        for row in rows:
            completeness = row.get("completeness_ratio")
            if completeness is None or completeness < policy.min_completeness_ratio:
                reason = "BELOW_COMPLETENESS_THRESHOLD"
                break
            gap = row.get("max_observed_gap_seconds")
            expected = row.get("expected_interval_seconds")
            if policy.max_observed_gap_seconds is not None and gap is not None \
                    and gap > policy.max_observed_gap_seconds:
                reason = "OBSERVED_GAP_EXCEEDS_LIMIT"
                break
            if gap is not None and expected is not None and expected > 0 \
                    and gap > expected * policy.max_expected_interval_multiple:
                reason = "OBSERVED_GAP_EXCEEDS_EXPECTED_INTERVAL"
                break
            if row.get("last_status") == "failure":
                reason = "LAST_OBSERVATION_FAILED"
                break
        results[chain] = ChainEligibility(chain, reason is None, reason, rows)
    return results
