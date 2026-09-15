# Phase 6 experiment-control closure matrix

This matrix freezes the executable Phase 6 governed experiment-control
contract (Slices 6.1-6.7). It records offline fixture evidence for declarative
specification, deterministic execution, versioned definitions, frozen
hypothesis families, verified catalog comparison, the local control API, and
their composition. It does not claim predictive alpha, profitability,
live-provider acceptance, or production-scale sample adequacy.

| Criterion | Evidence | Status |
| --- | --- | --- |
| Complete versioned experiment specification and deterministic identity | `tests/test_phase6.py` specification-schema tests cover every declared component, identity replay/change, and fail-closed cross-component validation. | PASS |
| Identical specification and data replay to one byte-identical immutable run | `tests/test_phase6_closure.py::test_phase6_replay_and_manifest_reconstruction_are_complete_and_offline` reconstructs the spec through the public loader, re-executes it against the same snapshot, and obtains the same verified run directory without network access. | PASS |
| Complete manifest reconstruction and artifact integrity | `tests/test_phase6_closure.py::test_phase6_replay_and_manifest_reconstruction_are_complete_and_offline` proves every run file is declared, every declared SHA-256 matches, the frozen family is present, and verified inspection succeeds. | PASS |
| Registered feature and label semantics are retained in row and run provenance | `tests/test_phase6.py` registry and definition-artifact tests cover semantic versions, definition identities, compatibility defaults, and per-row provenance. | PASS |
| Hypothesis family is frozen before evaluation and cannot be narrowed after results | `tests/test_phase6.py` hypothesis-family tests cover deterministic expansion, exact-grid enforcement, tamper rejection, and correction binding; the closure replay verifies the complete frozen family artifact. | PASS |
| Holdout evidence stays sealed from candidate scoring and promotion | `tests/test_phase6_closure.py::test_phase6_holdout_is_sealed_and_incompatible_comparison_fails_closed` changes only holdout prices and proves labels change while discovery-derived candidate and promotion artifacts remain byte-identical. | PASS |
| Methodologically incompatible runs cannot be compared | `tests/test_phase6.py` covers compatibility checks and `tests/test_phase6_closure.py::test_phase6_holdout_is_sealed_and_incompatible_comparison_fails_closed` composes the runner and catalog to reject a changed cost policy. | PASS |
| Local validate/run/inspect/approve boundary delegates to verified immutable contracts | `tests/test_phase6.py` control API and CLI tests cover schema rejection, runner delegation, verified inspection, separate immutable human approval, attribution, and tamper rejection. | PASS |
| Analysis acceptance remains local and offline | `tests/test_phase6_closure.py::test_phase6_replay_and_manifest_reconstruction_are_complete_and_offline` denies socket creation for the composed reconstruct/replay/inspect path. | PASS |

## Scope boundary

The current runner deliberately preserves unavailable multiplicity-test evidence
as unavailable, so fixture promotion remains `insufficient_evidence`; the closure
matrix does not convert that honest missingness into a successful research
claim. Phase 7 may add robust validation methods, but Phase 6 closure neither
automates optimization nor authorizes paper/live execution or publication.
