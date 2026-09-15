# AGENTS.md

## Purpose and scope

Applies to all of `analysis/`: `datasets/`, `backtesting/`, `strategies/`, `metrics/`, `runs/`, `alpha/`, and `experiments/`.

Analysis is offline research. It consumes persisted local data and immutable local artifacts; it does not call providers or mutate canonical ingestion data.

## Architecture and invariants

MUST NOT import or call ingestion/provider adapters, market APIs, exchanges, explorers, RPCs, telemetry, or other live network dependencies.

Dataset access MUST remain read-only. Preserve `DatasetSnapshot`'s point-in-time and ambiguity checks.

For any decision time `t`, only evidence observed/effective at or before `t` may influence the decision.

Unknown identity, duplicate identity, ambiguous bar source, ambiguous DEX quote asset, future evidence, invalid/non-finite values, or unsupported version semantics MUST fail closed or remain explicitly unavailable according to the current contract.

Never forward-fill across a temporal boundary unless an explicit registered policy authorizes it.

## Backtesting and strategies

Strategies emit intentions only. The simulator owns fills, cash, positions, fees, slippage, and order lifecycle.

The current simulator contract is long-only, single-venue CEX, next-available-bar-open execution with explicit missing/halted/stale policies.

MUST NOT silently add same-bar/intrabar execution, shorts, leverage, DEX/cross-venue execution, or alternative accounting semantics under the existing contract.

Metrics MUST derive from canonical simulator ledgers, not hidden strategy state.

Run artifacts MUST retain deterministic identities for inputs/configuration/code and fail on conflicting immutable overwrite.

## Alpha research

Cohorts MUST be defined before selecting winners. Keep cohort membership distinct from eligibility.

Candidates/chains without sufficient observed evidence remain excluded/ineligible with explicit reasons; absence of evidence is not a safe/healthy observation.

Features and labels MUST use registered versioned definitions with declared temporal/missing/horizon semantics.

Cross-version comparison MUST fail unless compatibility is explicitly declared.

If feature behavior changes while the callable body is excluded from its content identity, bump the catalog version; this is a required review discipline even where not mechanically enforced.

Discovery, validation, and holdout partitions MUST remain separated and leakage-resistant.

Promotion MUST advance only through the implemented sequential evidence gates. Missing required evidence is insufficient evidence, not success. Holdout remains sealed until eligible.

## Experiments

Experiment specs/runs MUST remain declarative, local, deterministic, validated against registered contracts, content-addressed, and immutable on conflict.

Do not invent unavailable statistical evidence or hidden executable selection behavior.

There is no repository-supported experiment CLI in the current codebase; do not fabricate one.

## Change boundaries

MUST NOT mutate canonical DuckDB data from analysis.

MUST NOT introduce live/paper trading, wallet/signing, automated execution, provider acquisition, or publication behavior.

MUST NOT describe fixture/replay success as predictive alpha, profitability, or production readiness.

## Testing requirements

Choose focused tests by subarea:

```bash
python -m pytest tests/test_phase2.py
python -m pytest tests/test_phase3.py tests/test_eligibility.py
python -m pytest tests/test_phase6.py
```

Temporal, leakage, deterministic replay, missing/censoring, compatibility, promotion, and immutable-artifact failure cases MUST be tested when their contracts change.

Analysis acceptance tests MUST remain offline; live socket use is a regression unless a separately approved architecture changes the boundary.

## Completion criteria

An analysis change is complete only when point-in-time semantics, identity/source disambiguation, deterministic replay, explicit missingness, version compatibility, and the applicable simulation/research gates remain intact and focused plus repository-wide verification passes.
