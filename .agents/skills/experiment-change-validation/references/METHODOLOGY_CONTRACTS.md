# Methodology Contracts

Load this reference when the classifier reports any experiment-methodology contract family or when inspection shows a transitive methodological effect.

## Contract map

| Family | Primary repository surface | Required reasoning / invariants |
| --- | --- | --- |
| Point-in-time evidence | `analysis/datasets/`, `analysis/alpha/features.py`, `analysis/alpha/evaluation.py` | Evidence observed/effective after decision time must not influence a decision; ambiguous/future evidence fails closed or remains unavailable. |
| Cohort / eligibility | `analysis/alpha/cohort.py`, `analysis/alpha/eligibility.py` | Cohort definition precedes winner selection; membership is distinct from eligibility; insufficient observed evidence remains excluded with explicit reason. |
| Feature semantics | `analysis/alpha/features.py`, `analysis/alpha/registry.py` | Registered/versioned definitions; declared missing/temporal semantics; changed behavior requires semantic version/identity discipline when code is not directly hashed. |
| Label semantics | `analysis/alpha/labels.py` | Registered/versioned horizon semantics; labels may depend on future outcome windows only as declared labels, never as decision-time features. |
| Split / leakage | `analysis/alpha/evaluation.py`, `analysis/experiments/spec.py`, `analysis/experiments/walk_forward.py` | Chronological discovery/validation/holdout separation; purge/embargo/lookback/horizon compatibility; no leakage between folds/partitions. |
| Promotion / holdout | `analysis/alpha/evaluation.py`, experiment control/approval boundaries | Sequential discovery → validation → sealed-holdout evidence gates; holdout remains sealed until eligible; missing evidence never counts as confirmation. |
| Multiplicity / hypotheses | `analysis/experiments/spec.py`, `analysis/experiments/hypotheses.py` | Family fixed before evaluation; declared correction identities/thresholds remain aligned with promotion policy; no post-result family redefinition. |
| Candidate scoring / costs / baselines | `analysis/experiments/spec.py`, `analysis/experiments/runner.py` | Declarative candidate identity; mandatory baselines preserved; cost/turnover scenarios are versioned and do not silently disappear; selection behavior resolves through canonical registry/code. |
| Uncertainty / censoring | `analysis/experiments/uncertainty.py`, alpha eligibility/evaluation | Unsupported/missing/censored evidence remains explicit; uncertainty policy is versioned/validated and cannot silently map missing evidence to favorable state. |
| Backtest execution | `analysis/backtesting/`, strategies/metrics | Strategies emit intentions only; simulator owns fills/accounting; next-available-bar-open, venue, long-only, missing/stale/halted semantics remain explicit unless a separately authorized contract changes. |
| Experiment spec identity | `analysis/experiments/spec.py` | Canonical serialized spec content deterministically identifies an experiment; semantically relevant fields/versions are represented. |
| Run / artifact identity | `analysis/alpha/artifacts.py`, experiment catalog/runner, run artifacts | Same canonical inputs/config/code identity ⇒ same ID; semantic change ⇒ identity change where required; conflicting immutable overwrite fails. |
| Compatibility | registries, specs, evaluation | Unsupported versions fail; cross-version comparison is rejected unless compatibility is explicitly declared. |
| Offline boundary | all `analysis/` | No provider/exchange/explorer/RPC/network acquisition; datasets are read-only; fixture/replay validation must not be described as live verification. |

## Transitive-impact rules

Treat a family as at least `TRANSITIVELY_AFFECTED` when a changed object is consumed by that family even if the primary file is untouched. In particular:

- `ExperimentSpec` changes can affect identity, split semantics, hypotheses, promotion compatibility, runner behavior, and artifact identity.
- Feature registry changes can affect experiment spec validation and every run resolving the changed feature version.
- Label horizon changes can affect split safety even when split code is untouched.
- Promotion policy changes can affect holdout access and the interpretation of candidate validation state.
- Runner/catalog serialization changes can affect reproducibility/immutability even if statistical calculations are unchanged.
- Backtest execution semantics can affect any experiment that uses backtest-derived candidate evidence or baselines.

## Version-bump discipline

Do not mechanically demand a version bump for every edit. Require one when the repository's identity contract depends on a version token to represent changed behavior that is not itself content-addressed.

For feature behavior specifically, `analysis/AGENTS.md` establishes that if executable behavior changes while the callable body is excluded from content identity, the catalog version must be bumped. A passing hash-only test is insufficient if the version remained stale.

## Evidence standard

A contract is `PASS` only when evidence could realistically detect the relevant failure. Examples:

- Temporal contract: construct/retain a future observation and prove it is rejected/ignored according to contract.
- Split contract: prove purge/embargo and horizon/lookback geometry prevents overlap/leakage.
- Holdout contract: prove holdout cannot be consumed before eligible promotion state.
- Identity contract: compare same-input and changed-semantic-input identities, plus conflicting overwrite behavior.
- Uncertainty contract: prove missing/unsupported evidence remains unavailable or rejected rather than defaulting favorable.
