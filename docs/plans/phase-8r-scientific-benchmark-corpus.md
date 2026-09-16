# Phase 8R.2 — Scientific benchmark corpus

The corpus is a deterministic, offline contract for methodology behavior. It
is not a profitability benchmark and does not use provider or network data.

`python -m analysis.benchmarks` prints its version, content identity, and the
12 declared cases. `tests/test_benchmark_corpus.py` verifies the stable case
set, the three dispositions (`pass`, `reject`, and `block`), immutable result
validation, and CLI replayability. The cases are intentionally named for the
existing governed boundaries so later benchmark probes can attach to the
canonical snapshot, label, split, promotion, and robustness implementations.

The corpus identity changes when a case, purpose, or expected disposition
changes. A passing benchmark is evidence that the declared offline oracle was
run; it is not evidence of predictive alpha, completeness of live data, or
execution readiness.
