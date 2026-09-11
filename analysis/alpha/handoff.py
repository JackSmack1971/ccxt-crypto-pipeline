from __future__ import annotations

def phase2_strategy_spec(candidate: dict, *, dataset_identity: str, feature_policy: str,
                         labels: tuple[str, ...] = ("1h", "6h", "24h", "7d"), split: dict | None = None) -> dict:
    """Return an intention-only Phase 2 handoff; execution remains next_bar_open."""
    return {"spec_version": "phase3-candidate-v1", "candidate": candidate, "dataset_identity": dataset_identity,
            "feature_policy": feature_policy, "labels": list(labels), "evaluation_split": split or {},
            "execution": "next_bar_open", "signals_are": "target_positions", "quote_currency": "USD",
            "live_execution": False, "validated_alpha": False}
