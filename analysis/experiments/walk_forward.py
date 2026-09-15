"""Deterministic, purged walk-forward fold construction.

The final 20 percent of the ordered cohort is always reserved as the sealed
holdout.  Earlier observations form expanding training windows followed by
non-overlapping validation windows.  Purge and embargo rules are applied at
every fold boundary and at the sealed-holdout boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train: tuple[str, ...]
    validation: tuple[str, ...]
    train_end: str
    validation_end: str
    removed: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class WalkForwardEvaluation:
    version: str
    folds: tuple[WalkForwardFold, ...]
    sealed_holdout: tuple[str, ...]
    holdout_removed: tuple[dict[str, str], ...]
    holdout_boundary: str
    embargo_days: int
    feature_lookback_seconds: int
    label_horizon_seconds: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_walk_forward_evaluation(cohort: tuple[Any, ...], *, folds: int,
                                  embargo_days: int, feature_lookback: timedelta,
                                  label_horizon: timedelta) -> WalkForwardEvaluation:
    """Build expanding, non-overlapping validation folds without holdout access."""
    if folds < 2:
        raise ValueError("walk-forward evaluation requires at least two folds")
    if embargo_days < 0 or feature_lookback < timedelta(0) or label_horizon < timedelta(0):
        raise ValueError("walk-forward temporal windows must be non-negative")
    ordered = sorted(cohort, key=lambda row: (row.t0, row.token_id))
    holdout_start = int(len(ordered) * .8)
    if holdout_start == len(ordered):
        raise ValueError("walk-forward evaluation requires a non-empty sealed holdout")
    pre_holdout = ordered[:holdout_start]
    # One initial training block plus one block per validation fold.
    block = len(pre_holdout) // (folds + 1)
    if block < 1:
        raise ValueError("insufficient cohort rows for configured walk-forward folds")
    embargo = timedelta(days=embargo_days)
    fold_results: list[WalkForwardFold] = []

    def remove(rows: list[Any], *, boundary: Any, earlier: bool, partition: str,
               removed: list[dict[str, str]]) -> tuple[str, ...]:
        kept = []
        for row in rows:
            reason = None
            if earlier and row.t0 + label_horizon >= boundary.t0:
                reason = "LABEL_WINDOW_OVERLAP"
            elif not earlier and row.t0 - feature_lookback < boundary.t0:
                reason = "FEATURE_WINDOW_OVERLAP"
            elif not earlier and embargo and row.t0 < boundary.t0 + embargo:
                reason = "EMBARGO"
            if reason:
                removed.append({"token_id": row.token_id, "partition": partition,
                                "reason": reason, "boundary_timestamp": boundary.t0.isoformat()})
            else:
                kept.append(row.token_id)
        return tuple(kept)

    for index in range(folds):
        validation_start = block * (index + 1)
        validation_stop = block * (index + 2) if index < folds - 1 else len(pre_holdout)
        boundary = pre_holdout[validation_start]
        removed: list[dict[str, str]] = []
        train = remove(pre_holdout[:validation_start], boundary=boundary, earlier=True,
                       partition="train", removed=removed)
        validation_rows = pre_holdout[validation_start:validation_stop]
        validation = remove(validation_rows, boundary=boundary, earlier=False,
                            partition="validation", removed=removed)
        if index == folds - 1:
            retained = [row for row in validation_rows if row.token_id in validation]
            validation = remove(retained, boundary=ordered[holdout_start], earlier=True,
                                partition="validation", removed=removed)
        fold_results.append(WalkForwardFold(index + 1, train, validation,
                                            boundary.t0.isoformat(),
                                            pre_holdout[validation_stop - 1].t0.isoformat(),
                                            tuple(removed)))
    holdout_boundary = ordered[holdout_start]
    holdout_removed: list[dict[str, str]] = []
    sealed_holdout = remove(ordered[holdout_start:], boundary=holdout_boundary, earlier=False,
                            partition="sealed_holdout", removed=holdout_removed)
    return WalkForwardEvaluation("phase7-walk-forward-v1", tuple(fold_results), sealed_holdout,
                                 tuple(holdout_removed),
                                 holdout_boundary.t0.isoformat(), embargo_days,
                                 int(feature_lookback.total_seconds()), int(label_horizon.total_seconds()))
