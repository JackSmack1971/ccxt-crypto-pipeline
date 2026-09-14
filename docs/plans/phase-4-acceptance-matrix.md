# Phase 4 acceptance matrix

This matrix freezes the executable Phase 4 reporting contract at the Phase 4R
closure boundary. Packages remain local drafts with a mandatory human-review
gate; this evidence does not authorize publication.

| Criterion | Evidence | Status |
| --- | --- | --- |
| Canonical immutable approved input | `tests/test_phase4.py::test_approved_handoff_is_deterministic_and_does_not_mutate_phase3_run`, `test_approved_handoff_rejects_changed_staged_artifact`, and `test_phase4_rejects_unknown_handoff_fields`. | PASS |
| Deterministic package replay and checksums | `tests/test_phase4.py::test_phase4_replay_is_byte_identical_and_review_gated` compares every generated artifact byte-for-byte and retains pending review. | PASS |
| Evidence-derived numeric and comparative claims | `tests/test_phase4.py::test_phase4_rejects_numeric_claim_that_disagrees_with_evidence` and `test_phase4_comparative_claim_derives_direction` prove declared derivations rather than evidence pointers alone. | PASS |
| Unresolved or mismatched provenance fails closed | `tests/test_phase4.py::test_phase4_rejects_unresolved_numeric_claim`, `test_phase4_rejects_claim_with_mismatched_dataset_identity`, `test_phase4_rejects_changed_research_manifest`, and `test_phase4_rejects_changed_staged_content`. | PASS |
| Chart semantics and missingness | `tests/test_phase4.py::test_phase4_chart_semantics_fail_closed_and_identity_is_retained` rejects unknown transformations and annotations; `test_phase4_missing_chart_values_are_explicit_not_zero` prevents fabricated zero values. | PASS |
| Structural SVG accessibility | `tests/test_phase4.py::test_phase4_replay_is_byte_identical_and_review_gated` exercises the repository-selected validator for SVG role, title, description, dimensions, units, attribution, and explicit missing state during generation. | PASS |
| Methodology, limitations, and exact inputs | `reporting/package/generate.py` builds methodology and limitations from the approved manifest and records research-run, manifest, dataset, code/config, time-range, renderer, validation, and checksum evidence in the package manifest. | PASS |
| Secret and local-path protection | `tests/test_phase4.py::test_phase4_requires_approval_and_scans_secrets` covers the generation gate; the repository reporting guard statically checks provider imports and secret/path protections. | PASS |
| Offline end-to-end review package | `tests/test_phase4.py::test_offline_phase1_to_phase4_chain_is_content_addressed_and_review_gated` denies socket creation and uses the canonical handoff builder across persisted launch data, features, labels, an explicit governed candidate decision, immutable research artifacts, approval, and pending-review package generation. | PASS |
| Publication boundary | Generated `review.json` and `package-manifest.json` remain `pending`; no reporting component publishes, uploads, or changes the approval into publication authorization. | PASS |

## External evidence kept separate

External publication approval and any live-provider acceptance are intentionally
outside Phase 4. They remain **BLOCKED** unless separately authorized; neither
is required for deterministic local review-package acceptance.

