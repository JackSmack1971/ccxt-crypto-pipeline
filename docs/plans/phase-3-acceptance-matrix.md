# Phase 3 acceptance matrix

This matrix freezes the executable Phase 3 research contract at the Phase 4R
closure boundary. It records methodology and fixture evidence; it does not
claim predictive alpha, profitability, production readiness, or live-provider
coverage.

| Criterion | Evidence | Status |
| --- | --- | --- |
| Deterministic cohort, feature, label, ranking, and artifact replay | `tests/test_phase3.py::test_temporal_alignment_rejects_permuted_labels_and_artifacts_replay_identically`, `test_research_run_identity_changes_when_evidence_content_changes`, and `test_phase1_to_phase3_replay_uses_persisted_snapshot_and_is_deterministic`. | PASS |
| Complete cohort inclusion/exclusion provenance | `tests/test_phase3.py::test_cohort_deduplicates_launches_and_preserves_liquidity_exclusion` retains each observed candidate, eligibility decision, reason, event source, and dataset identity. | PASS |
| Point-in-time features and lineage | `tests/test_phase3.py::test_feature_registry_carries_temporal_contract_and_rejects_future_definition`, `test_future_source_timestamp_is_rejected_and_policy_filters_bars`, and `test_symbol_only_identity_is_an_exclusion_and_late_lineage_is_invisible`. | PASS |
| Address-scoped token/market identity | `tests/test_phase3.py::test_pool_constituents_are_address_scoped_and_relationships_are_point_in_time` proves two constituent identities and rejects relationships not yet observed. | PASS |
| Fixed-horizon labels, censoring, and quote conversion | `tests/test_phase3.py::test_labels_use_fixed_horizon_and_report_right_censoring`, `test_unavailable_quote_conversion_is_explicit_censoring`, `test_non_usd_labels_use_temporally_valid_conversion_provenance`, and `test_non_usd_quote_without_conversion_fails_closed_and_stablecoin_parity_is_explicit`. | PASS |
| Purged chronological discovery/evaluation split | `tests/test_phase3.py::test_split_is_chronological_sealed_and_corrections_are_recorded` and `test_split_purges_feature_and_label_windows_at_fixed_boundaries` cover fixed boundaries, purge/embargo evidence, and sealed holdout membership. | PASS |
| Leakage gate | `tests/test_phase3.py::test_temporal_alignment_rejects_permuted_labels_and_artifacts_replay_identically` rejects a deliberately permuted label; the future-source and late-lineage tests reject future information. | PASS |
| Baselines, uncertainty, costs, and governed promotion | `tests/test_phase3.py::test_candidate_cannot_be_confirmed_from_coverage_alone` and `test_candidate_promotion_requires_every_stage_gate_and_is_preserved_by_registry` require corrected significance, replication, baseline/effect uncertainty, cost sensitivity, and sealed-holdout evidence. | PASS |
| Phase 2-compatible handoff | `tests/test_phase3.py::test_candidate_low_coverage_is_not_validated_alpha_and_handoff_is_phase2_compatible` preserves next-bar-open execution and intention-only strategy semantics. | PASS |
| Offline persisted-input execution | `tests/test_phase3.py::test_phase1_to_phase3_replay_uses_persisted_snapshot_and_is_deterministic` denies socket creation while loading the local DuckDB snapshot and writing content-addressed research artifacts. | PASS |

## External evidence kept separate

Live-provider coverage and production-shaped longitudinal sample adequacy are
not Phase 3 fixture acceptance criteria. They remain **BLOCKED** on separately
authorized live ingestion runs and credentials. No Phase 3 result is therefore
represented as validated profitability or production readiness.

