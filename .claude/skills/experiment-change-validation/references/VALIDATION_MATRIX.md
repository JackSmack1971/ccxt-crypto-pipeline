# Validation Matrix

Use this reference to select the narrowest executable checks that cover the affected contracts. Confirm current test names/content before relying on a command; repository tests are authoritative and can evolve.

## Current focused anchors

| Changed / affected surface | Minimum focused anchor | Usually pair with |
| --- | --- | --- |
| `analysis/backtesting/`, strategies, metrics, run semantics | `python -m pytest tests/test_phase2.py` | targeted node IDs for changed simulator/strategy behavior |
| alpha cohort/features/labels/evaluation/promotion | `python -m pytest tests/test_phase3.py` | `tests/test_eligibility.py` when eligibility/provider-quality semantics are affected |
| `analysis/alpha/eligibility.py` | `python -m pytest tests/test_eligibility.py tests/test_phase3.py` | phase 6 when experiment eligibility resolution is affected |
| `analysis/experiments/` spec/runner/catalog/control/hypotheses/uncertainty/walk-forward | `python -m pytest tests/test_phase6.py` | phase 3 when shared alpha contracts/registries/promotion are affected |
| shared alpha registry or label semantics consumed by experiments | `python -m pytest tests/test_phase3.py tests/test_phase6.py` | eligibility tests if chain/candidate eligibility is involved |
| experiment CLI semantics | targeted CLI tests in `tests/test_phase6.py` | root compile/import check if module/public API changed |

These are anchors, not exhaustive mandates. Inspect test coverage and add the smallest targeted node IDs required to exercise a newly changed boundary.

## Mandatory test dimensions by contract

When the corresponding contract changes, ensure focused evidence covers these dimensions even if that requires adding/updating tests before validation can pass:

- temporal: future evidence rejection / point-in-time filtering;
- leakage: split ordering, purge/embargo, label-horizon and feature-lookback interaction;
- deterministic replay/identity: repeated same-input equality and semantically changed-input inequality;
- missing/censoring: explicit unavailable/fail-closed behavior;
- compatibility: unsupported/cross-version behavior;
- promotion: each relevant sequential state and premature holdout rejection;
- immutable artifacts: idempotent identical write and conflicting overwrite rejection;
- uncertainty: declared policy semantics under insufficient evidence;
- multiplicity: hypothesis-family freeze and correction-policy alignment;
- backtesting: execution timing, fills/accounting ownership, stale/missing/halted behavior when touched.

## Broadening decision

Do **not** broaden just because focused tests pass. Broaden when repository policy or observed risk requires it. Typical reasons:

1. A shared public API or serialization format changed.
2. A registry/versioned definition is consumed by multiple phases.
3. The focused suite exposes an unexpected failure outside its nominal scope.
4. A change affects importability across packages.
5. Repository completion policy explicitly requires a broader gate.

Current root configured gates include the full pytest suite, compileall over repository Python packages/tests, and `git diff --check`. Do not invent extra linters/type-checkers/security scans as required gates unless repository configuration/authority adds them.
