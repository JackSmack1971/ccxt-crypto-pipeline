# Phase 2 acceptance matrix

This matrix records the evidence for the implemented first slice of the Phase 2
backtesting framework. It does not authorize live or paper execution, strategy
optimization, alpha discovery, or external publication.

| Criterion | Evidence | Status |
| --- | --- | --- |
| Deterministic replay | `tests/test_phase2.py::test_replay_artifacts_are_byte_identical`; `analysis/runs/artifacts.py` derives a content-addressed run ID and refuses conflicting rewrites. | PASS |
| Point-in-time access | `tests/test_phase2.py::test_point_in_time_metadata_and_next_bar_fee_slippage`; `DatasetSnapshot.metadata_at()` returns unavailable for future observations. | PASS |
| Next-bar execution and costs | `tests/test_phase2.py::test_point_in_time_metadata_and_next_bar_fee_slippage`; fill records contain fee and slippage, and metrics aggregate both. | PASS |
| Duplicate, missing, halted, and insufficient bars | `tests/test_phase2.py::test_duplicate_bars_are_rejected` and `test_missing_halted_and_insufficient_bars_are_explicit`; simulator policies produce explicit rejection/skip outcomes. | PASS |
| Offline fixture execution and provenance | `tests/test_phase2.py` uses local DuckDB/Parquet fixtures; `test_replay_artifacts_are_byte_identical` writes manifest and ledger artifacts with dataset, policy, strategy, simulator, and code inputs. | PASS |
| Actionable rejection | `tests/test_phase2.py::test_unknown_identity_is_rejected`, `test_unsupported_execution_is_actionable`, and `test_non_positive_execution_price_is_rejected`. | PASS |
| Artifact secret handling | `tests/test_phase2.py::test_run_manifest_redacts_credential_fields` and `test_failed_run_is_recorded_without_result_artifacts`; field secrets, URL credentials, and failed-run details are sanitized. | PASS |

## Verification record

The acceptance run was executed with:

```text
uv run python -m pytest
uv run python -m compileall -q analysis ingestion normalization scheduler storage
git diff --check
```

Observed result: `39 passed`; compilation and diff checks passed. The analysis
package contains no imports of provider adapters or ingestion modules. The
fixture path uses only local persisted inputs and remains separate from the
provider-facing ingestion boundary.

The resolved first-slice decisions remain documented in
`phase-2-backtesting-strategy-framework.md`; open decisions not resolved there
remain out of scope.
