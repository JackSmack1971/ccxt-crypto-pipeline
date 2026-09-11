from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

def research_report(*, cohort, labels=(), candidates=(), split=None, hypotheses=(), dataset_identity: str = "") -> str:
    rows = [asdict(x) if is_dataclass(x) else x for x in cohort]
    label_rows = [asdict(x) if is_dataclass(x) else x for x in labels]
    candidate_rows = [asdict(x) if is_dataclass(x) else x for x in candidates]
    included = sum(bool(x.get("included")) for x in rows); excluded = len(rows) - included
    chain_counts = {}
    for row in rows: chain_counts[row.get("chain", "unknown")] = chain_counts.get(row.get("chain", "unknown"), 0) + 1
    candidate_lines = []
    for candidate in candidate_rows:
        candidate_lines.append(
            f"- `{candidate.get('name')}` / {candidate.get('horizon')}: "
            f"n={candidate.get('sample_size')}, independent launches={candidate.get('independent_launches')}, "
            f"coverage={candidate.get('coverage')}, missingness={candidate.get('missingness')}, "
            f"mean log return={candidate.get('mean_return')}, "
            f"promotion_state={candidate.get('promotion', {}).get('state', 'discovered')}")
    split = split or {}
    split_line = (f"- Split: chronological discovery/validation/sealed holdout; actual membership applies "
                  f"a {split.get('embargo_days', 'unspecified')}-day embargo, "
                  f"{split.get('feature_lookback_seconds', 'unspecified')}s feature lookback, and "
                  f"{split.get('label_horizon_seconds', 'unspecified')}s label horizon "
                  f"({len(split.get('removed', []))} rows removed).")
    return "\n".join(["# Phase 3 research report", "", "## Provenance", f"- Dataset identity: `{dataset_identity}`",
        "- Scope: descriptive/baseline research only; not an investment recommendation.", "", "## Cohort",
        f"- Detected launches: {len(rows)}", f"- Included: {included}", f"- Excluded: {excluded}",
        f"- Independent launches: {len({x.get('token_id') for x in rows})}", f"- Chain composition: {chain_counts}",
        "- Primary liquidity gate: USD-equivalent liquidity >= $10,000 at t0; sensitivities: $5,000/$25,000/$50,000.",
        "- Coverage gate: >=80% of expected observations and no contiguous gap >25% of the interval.", "", "## Labels and candidates",
        f"- Label rows: {len(label_rows)}", f"- Candidate rows: {len(candidate_rows)}", f"- Hypotheses tested: {len(hypotheses)}",
        "- Horizons: 1h, 6h, 24h, 7d; labels are log forward returns in USD with explicit economic/data/right censoring.",
        split_line,
        "- Multiple testing: Benjamini-Hochberg FDR q=0.05 for discovery; Holm-Bonferroni alpha=0.05 for confirmation.",
        "- Uncertainty, missingness, cost sensitivity, and independent-launch counts are retained in candidate artifacts.", "",
        "## Candidate ranking", *(candidate_lines or ["- No candidate results were supplied."]),
        "- Promotion requires corrected discovery, frozen validation replication, sealed-holdout confirmation, baseline, uncertainty/effect-size, and cost gates; this report does not claim predictive alpha.", "",
        "## Reproducibility payload", "```json", json.dumps({"dataset_identity": dataset_identity, "split": split,
        "cohort": rows, "labels": label_rows, "candidates": candidate_rows, "hypotheses": hypotheses}, default=str, sort_keys=True, indent=2), "```", ""])
