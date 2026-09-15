# Mutmut test-improvement plan

Status: U1–U7 implemented; a fresh complete mutation campaign remains blocked by the local
WSL environment and is not claimed as a mutation-score result.

## Execution update — 2026-09-14

U1 (simulator validation boundary matrix) and U2 (timeframe parser contract) were implemented
in `tests/test_phase2.py` and committed as `6c3e02e`. The focused Phase 2 suite passed 53 tests.
The next logical slice is U3, focused on simulator-observable order, ledger, rejection, and
edge-case behavior. It remains test-only: no simulator behavior or mutation configuration is
being changed. The full repository suite still has the five pre-existing Phase 5/storage
failures recorded in the prior handoff.

U3 was then implemented in the same Phase 2 test module. The added cases cover empty datasets,
cross-venue and explicit venue rejection, scripted buy/sell ledger transitions, cash
conservation, invalid and short targets, insufficient cash, all stale-signal policies, and
final pending orders. The focused suite passed 64 tests; the full suite passed 211 tests with
the same five pre-existing Phase 5/storage failures. U3 is complete for this test-only slice;
the next planned work is U4 unless refreshed mutation evidence changes prioritization.

## Execution update — 2026-09-14 (U4 active)

U4 is the active test-only slice. It targets the meaningful pure/helper contracts in
`ingestion/cex/common.py` and `ingestion/cex/backfill.py`: YAML configuration shape validation,
clear unsupported-exchange errors, rate-limit construction, and `_parse_since` handling for
ISO dates, timezone-aware timestamps, epoch-like values, and malformed input. Tests remain
offline and provider construction is mocked. No production behavior or mutmut configuration
is changed by this slice.

U4 was implemented in `tests/test_cex.py`: mapping and empty/non-mapping YAML cases, unsupported
exchange rejection, rate-limit construction, three ISO/timezone parsing cases, and rejection of
epoch-like or malformed values. The focused suite passed 14 tests with
`uv run --no-sync python -m pytest tests/test_cex.py -q`. A full-suite attempt reached 206 passed
tests but also reported existing failures and pytest setup/storage errors after the local temp
volume exhausted its space; that run is not treated as a clean full-suite gate. No production
files or mutmut configuration were changed.

## Execution update — 2026-09-14 (U5 active)

U5 is the next test-only slice. It will exercise the public CEX refresh, universe, and backfill
orchestration seams with mocked collaborators and temporary local storage. The cases will cover
CLI/config path precedence, refresh ticker and candle requests, checkpoint-plus-timeframe resume,
empty/short candle filtering, run success/failure logging, exchange cleanup, and exception
propagation. Parser boilerplate without independent repository behavior remains out of scope.

U5 was implemented in `tests/test_cex.py`: refresh now has assertions for one exchange-wide
ticker snapshot, checkpoint-plus-timeframe resume, short-candle filtering, successful ledger
logging, failure propagation, and cleanup; backfill has exact persisted-checkpoint arithmetic,
short-candle filtering, and cleanup coverage; and the three public CLI wrappers have config/path
precedence checks where their orchestration is observable. The focused suite passed 20 tests with
`uv run --no-sync python -m pytest tests/test_cex.py -q`. The provisioned full suite passed 228
tests and retained the five pre-existing Phase 5/storage failures; bare `python -m pytest` was
not runnable because the system interpreter lacks repository dependencies such as DuckDB. No
production files or mutmut configuration were changed. U5 is complete for this test-only slice;
the next planned work is U6 unless refreshed mutation evidence changes prioritization.

## Execution update — 2026-09-14 (U6 complete)

U6 was implemented in `tests/test_phase3.py`. The added cases cover launch-liquidity propagation,
two-point logarithmic returns, inclusive lookback endpoints, insufficient valid bars, invalid and
non-positive closes, and `DatasetSnapshot.events_at` exact canonical-identity matching with
boundary inclusion and future/other-identity exclusion. The focused suite passed 29 tests with
`uv run --no-sync python -m pytest tests/test_phase3.py -q`. This remains a test-only slice: no
production files, persistence schema, or mutmut configuration were changed. Refreshed campaign
evidence is not claimed because the prior WSL campaign was incomplete; these tests are the
targeted remediation for the U6 historical no-test seams. The provisioned full suite completed
with 235 passed and the same five pre-existing Phase 5/storage failures; bare `python -m pytest`
could not collect because the system interpreter lacks repository dependencies including DuckDB
and APScheduler.

## Execution update — 2026-09-14 (U7 complete)

U7 added the next narrow Phase 3 contract coverage in `tests/test_phase3.py`: launch-liquidity
unknown/zero/reject policy behavior, custom close-return naming with invalid observations ignored,
and deterministic chronological ordering from `DatasetSnapshot.events_at` when input events are
unsorted. The focused suite passed 34 tests with
`uv run --no-sync python -m pytest tests/test_phase3.py -q`. This remains test-only and does not
claim refreshed mutation results. The system interpreter still cannot collect because DuckDB and
APScheduler are unavailable, and WSL cannot start because its virtual disk is missing; therefore
the fresh POSIX mutmut campaign required by the execution contract remains blocked. The
provisioned full-suite result remains 235 passed with the same five pre-existing Phase 5/storage
failures. The next action is to restore the POSIX environment, run the complete current campaign,
and reconcile terminal survivors/no-test/timeout results before claiming any score change.

## Evidence boundary

The artifact inspected was `/mutants`, especially `mutants/mutmut-stats.json` and the
`*.py.meta` / `*.py.spans` files. The campaign used mutmut 3.8.0 and the repository mutmut
configuration:

```toml
source_paths = ["analysis", "ingestion", "normalization", "reporting", "scheduler", "storage"]
pytest_add_cli_args_test_selection = ["tests"]
also_copy = [".github/", "scripts/", "config/"]
```

The campaign generated 11,435 mutants. Only 814 have a terminal result:

| Result | Count | Interpretation |
| --- | ---: | --- |
| killed | 254 | A selected test detected the mutant |
| survived | 153 | A selected test ran but did not detect the mutant |
| no tests | 404 | The selected tests did not exercise the mutant |
| timeout | 3 | `analysis.backtesting.simulator.simulate` mutants 82, 87, and 88 |
| not checked | 10,621 | No conclusion; do not treat as survivors or as covered |

The 153 survivors are concentrated in three simulator seams:

| Production seam | Survivors | Main gap |
| --- | ---: | --- |
| `analysis/backtesting/simulator.py:BacktestConfig.validate` | 22 | Boundary and validation assertions are too permissive |
| `analysis/backtesting/simulator.py:_bar_interval` | 18 | Timeframe parsing lacks a compact boundary matrix |
| `analysis/backtesting/simulator.py:simulate` | 113 | Ledger/order/error behavior is not asserted deeply enough |

The 404 no-test outcomes are concentrated in these seams:

| Production seam | No-test mutants |
| --- | ---: |
| `ingestion/cex/refresh.py:refresh_exchange` | 172 |
| `ingestion/cex/backfill.py:main` | 85 |
| `analysis/alpha/features.py:close_return_feature` | 35 |
| `ingestion/cex/refresh.py:main` | 25 |
| `ingestion/cex/universe.py:main` | 23 |
| `analysis/alpha/features.py:launch_liquidity_feature` | 19 |
| `ingestion/cex/common.py:load_config` | 12 |
| `ingestion/cex/common.py:create_exchange` | 11 |
| `analysis/datasets/snapshot.py:events_at` | 11 |
| `ingestion/cex/backfill.py:_parse_since` | 11 |

The campaign was recorded against commit `292852b0e6eae3bbc271b204f91e8eb4779b424e`,
while current `HEAD` is `ffc39309897da17796925397a592b27f07891dbb`. These results are
historical diagnostics only; do not execute the plan against them as current evidence.

## Execution contract

1. Preserve existing working-tree changes. Do not apply or edit files inside `/mutants`.
2. Run the repository baseline command, `python -m pytest`, and record the result.
3. Run a fresh mutmut campaign at the exact implementation base commit, preferably in a
   supported POSIX environment because mutmut 3.x requires POSIX `fork` and does not provide
   reliable native-Windows execution.
4. Capture state fingerprints before and after the campaign with
   `.agents/skills/python-mutation-testing/python-mutation-testing/scripts/state_fingerprint.py`.
5. Reconcile the refreshed metadata. Every active `survived`, `no tests`, and timeout result
   gets an explicit disposition; the old counts are priorities, not a completion target.
6. Re-run each affected mutant after its targeted test change, then run the relevant regression
   tests. Finish with a complete current campaign; do not infer a package score from targeted
   reruns.

## Remediation units

### U1 — Simulator validation boundary matrix (P0)

Targets: `analysis/backtesting/simulator.py:BacktestConfig.validate` and existing
`tests/test_phase2.py` validation coverage. Historical survivor families: 5, 7–11, 15–18,
29–31, 37–41, and 45–48.

Add behavior-level cases for zero and negative `initial_cash`, `fee_rate`, and
`slippage_bps`; every invalid execution, bar-policy, stale-signal, and source-universe value;
and every valid supported value. Include actionable error-message fragments where that message
is part of the contract. The suite must fail if boolean guards are weakened or an allowed value
is removed, while retaining all documented valid configurations.

### U2 — Timeframe parser contract (P0)

Target: `analysis/backtesting/simulator.py:_bar_interval`; add a focused matrix in the Phase 2
tests. Cover `1m`, `1h`, `1d`, `1w`, multi-digit counts, zero and negative counts, missing
counts, unsupported units/case, malformed numeric text, and the exception type/message contract.
The expected duration must be asserted, not merely that parsing succeeds. This should kill the
18 historical survivors without coupling tests to mutmut-generated function names.

### U3 — Simulator observable ledger and rejection tests (P0)

Target: `analysis/backtesting/simulator.py:simulate`; extend the existing fixture builders in
`tests/test_phase2.py` or add the smallest adjacent test module.

Use tiny deterministic datasets and a controllable strategy to assert: empty datasets; CEX-only
and cross-venue selection; explicit venue mismatch; next-bar execution; stale pending signals
under `execute_next_available`, `skip`, and `error`; insufficient cash; invalid quantities;
short-position rejection; non-positive prices; halted bars; missing bars; final pending orders;
multi-asset equity marking; trade/order status, side, quantity, notional, fee, slippage, cash,
signal time, and execution time. Assert cash conservation and position transitions after both
buy and sell operations. Include one test that forces the three timeout mutants (82, 87, 88) to
finish quickly or records them as timeout-equivalence/operational findings after inspection.

The acceptance oracle is the Phase 2 contract: signal at close, earliest fill at next available
open, explicit unsupported/rejected outcomes, and deterministic ledger output. Avoid broad
snapshot assertions when a field-level assertion gives a clearer fault signal.

### U4 — CEX configuration and pure helper coverage (P1)

Targets: `ingestion/cex/common.py:load_config`, `create_exchange`, and
`backfill.py:_parse_since`; tests should live with `tests/test_cex.py`.

Add temporary-path configuration cases for a mapping, empty YAML, and non-mapping YAML; assert
unsupported exchange IDs fail clearly and supported construction receives the rate-limit option;
and parameterize ISO dates, timezone-aware timestamps, epoch-like values, and malformed values for
`_parse_since`. Keep provider calls mocked and offline.

### U5 — CEX refresh/universe/backfill orchestration (P1)

Targets: `refresh_exchange`, `refresh.main`, `universe.main`, and `backfill.main`.

Exercise public orchestration with `sys.argv` plus monkeypatched collaborators, or test the
callable orchestration directly where the CLI wrapper has no independent contract. Verify config
and CLI precedence, database/parquet paths, requested timeframes, checkpoint-plus-timeframe
resume arithmetic, empty/short candle filtering, run success/failure logging, exception
propagation, exchange cleanup, and no-live-network behavior. For refresh, assert one exchange-wide
ticker snapshot is requested and that valid candle rows are persisted with the right identity,
source, and timestamp. Do not add tests merely to execute argument-parser boilerplate if a
repository policy treats those wrappers as non-semantic; record that disposition explicitly.

### U6 — Alpha feature factories and point-in-time event lookup (P1)

Targets: `analysis/alpha/features.py:launch_liquidity_feature`,
`close_return_feature`, and `analysis/datasets/snapshot.py:events_at`.

Add cases for launch liquidity propagation, no bars, one valid bar, two valid bars, invalid or
non-numeric closes, non-positive closes, lookback inclusion at both endpoints, and logarithmic
return direction. For `events_at`, assert exact canonical identity matching and inclusion at the
decision timestamp while excluding future events. Preserve unknown rather than manufacturing
values. If the refreshed campaign still reports no-test mutants in pure factory code, prefer
direct contract tests; if only wrapper/defensive mutations remain, use `equivalence-review` with
an explicit rationale.

## Review and disposition rules

- `survived`: remediate when the mutation changes an observable behavior established by
  `AGENTS.md`, phase specifications, source code, or existing tests.
- `no tests`: first determine whether the code is a meaningful public/helper contract. Add a
  focused test for meaningful seams; classify parser-only or unreachable defensive branches only
  after an explicit repository-based equivalence review.
- `timeout`: reproduce individually with the narrowest affected test set. Treat a timeout as an
  operational failure until proven otherwise; do not count it as killed.
- `not checked`: remains untriaged pending a complete campaign. Never infer its behavior from
  the generated source copy alone.

Cluster tests by observable contract, not by mutant ID. A single test may kill many related
operator, boundary, or message mutants. Do not weaken assertions, change production behavior,
add mutation exclusions, or accept a higher score as evidence without a behavioral oracle.

## Definition of done for downstream agents

- The fresh campaign is bound to the current implementation commit and its baseline passes.
- Every terminal active mutant has a disposition; no stale or unchecked result is presented as
  final evidence.
- U1–U3 are complete before lower-risk coverage is prioritized, unless refreshed evidence removes
  their corresponding mutants.
- Targeted mutants are killed or documented as independently reviewed equivalent/operational
  cases, and `python -m pytest` passes.
- A complete current mutmut run is captured, including command, environment, state fingerprints,
  counts, timeout/no-test handling, and changed test files.
- No provider access, credentials, live trading, persistence migration, or production behavior
  change is introduced as part of test remediation.

## Campaign evidence — 2026-09-14

A fresh campaign was generated from commit `ffc39309897da17796925397a592b27f07891dbb` with
13,396 mutants. The selected mutmut baseline passed with `164 passed, 5 deselected`; the
unconstrained repository baseline was `164 passed, 5 failed`. The five deselected tests are
the pre-existing Phase 5/storage failures listed in the handoff notes above. The temporary
selection was used only to let mutmut execute and was restored to `pytest_add_cli_args_test_selection = ["tests"]`.

The campaign was run under WSL with Python 3.12, mutmut 3.8.0, and one worker. WSL terminated
three times before completion. The last persisted cache contained all 13,396 generated mutant
records, of which 4,705 were killed, 4,068 survived, 1,356 were classified as no-tests, 7
timed out, 5 exited suspiciously, and 3,255 remained unclassified. Because the unclassified
tail was not rerun to terminal completion, no complete fresh mutation score is claimed.

The generated caches and temporary virtual-environment artifacts were removed after the final
WSL failure to restore disk space and Git operability. This plan remains the durable downstream
handoff; the next run must recreate the cache from the restored configuration, capture before
and after state fingerprints, repair the five baseline failures (or explicitly document their
scope), and report the final score only when no active mutant remains unchecked.
