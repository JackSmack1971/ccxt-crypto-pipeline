# Phase 5 data-plane closure matrix

This matrix freezes the executable Phase 5 data-plane reliability contract
(Slices 5.1-5.7). It records fixture evidence for durable restart, gap
detection, reorg reconciliation, resumable discovery, provider quality/
eligibility gating, DuckDB/Parquet recovery, and reference-series-backed
conversion replay, and proves those guarantees compose in one local dataset
across representative EVM and Solana chains. It does not claim live-provider
acceptance or production-scale longitudinal sample adequacy.

| Criterion | Evidence | Status |
| --- | --- | --- |
| Durable EVM cursor restart, idempotent overlap replay | `tests/test_evm.py::test_listener_cursor_survives_restart_and_rejects_skipped_range`; `tests/test_phase5_closure.py::test_evm_cursor_restart_and_reorg_compose_and_gap_detection_fails_closed` composes restart with reorg reconciliation for one representative chain. | PASS |
| EVM gap detection fails closed rather than silently skipping blocks | `tests/test_evm.py::test_listener_cursor_survives_restart_and_rejects_skipped_range`; `tests/test_phase5_closure.py::test_evm_cursor_restart_and_reorg_compose_and_gap_detection_fails_closed` rejects a skipped range after a restart without advancing the cursor. | PASS |
| EVM reorg reconciliation without deleting historical evidence | `tests/test_evm.py::test_listener_reconciles_short_reorg_without_deleting_block_evidence`; `tests/test_phase5_closure.py::test_evm_cursor_restart_and_reorg_compose_and_gap_detection_fails_closed` reproduces the reorg, then restarts cleanly past the boundary. | PASS |
| Solana durable, resumable, multi-page discovery without silent high-activity loss | `tests/test_solana.py::test_run_once_pages_to_durable_signature_without_silent_high_activity_loss`; `tests/test_phase5_closure.py::test_phase5_data_plane_closure_across_representative_evm_and_solana_chains` replays the same multi-page scenario for the representative Solana chain feeding the composed dataset. | PASS |
| Solana gap detection fails closed without advancing progress | `tests/test_solana.py::test_run_once_fails_closed_when_durable_signature_cannot_be_reached`; `tests/test_phase5_closure.py::test_solana_gap_detection_fails_closed_without_advancing_progress`. | PASS |
| Provider observation ledger and offline quality summary | `tests/test_storage.py::test_provider_observation_log_tracks_gaps_and_offline_quality_summary`; `tests/test_scheduler.py::test_cycle_records_provider_observation_log_with_expected_intervals`. | PASS |
| Research-eligibility gate over persisted quality evidence, fail-closed for unobserved chains | `tests/test_eligibility.py` (healthy/unhealthy/unobserved/multi-scope policy coverage); `tests/test_phase3.py::test_cohort_excludes_a_chain_whose_provider_quality_fails_the_gate` and `test_cohort_keeps_prior_behavior_when_a_chain_has_no_eligibility_evidence`; `tests/test_phase5_closure.py::test_phase5_data_plane_closure_across_representative_evm_and_solana_chains` computes eligibility from real persisted observations for two healthy representative chains and one never-observed chain. | PASS |
| DuckDB authoritative / Parquet mechanically recoverable after a publication failure | `tests/test_storage.py::test_verify_parquet_publication_detects_missing_stale_and_unreadable_partitions` and `test_insert_ohlcv_batch_publication_failure_leaves_db_committed_and_mechanically_recoverable`; `tests/test_phase5_closure.py::test_phase5_data_plane_closure_across_representative_evm_and_solana_chains` detects and repairs a missing partition for one representative chain before research reads the recovered dataset. | PASS |
| Point-in-time reference series with provenance, offline coverage summary | `tests/test_storage.py::test_reference_series_round_trip_is_idempotent_and_offline_coverage_summary`; `tests/test_phase3.py::test_dataset_snapshot_exposes_point_in_time_reference_series`. | PASS |
| Forward-return labels source conversion from the persisted reference series across independent quote assets | `tests/test_phase3.py::test_generate_labels_sources_conversion_from_persisted_reference_series_without_explicit_observations`; `tests/test_phase5_closure.py::test_phase5_data_plane_closure_across_representative_evm_and_solana_chains` derives ETH/USD- and SOL/USD-backed labels for both representative chains from persisted series alone. | PASS |
| Composed data-plane guarantees hold together in one local dataset across representative chains, offline | `tests/test_phase5_closure.py::test_phase5_data_plane_closure_across_representative_evm_and_solana_chains` denies socket creation and threads durable-cursor restart, resumable discovery, eligibility gating, Parquet recovery, and reference-series replay through the real Phase 1 storage boundary into cohort extraction and label generation for two representative chains. | PASS |
| Malformed/unresolved event identity does not corrupt a resolved cohort member | `tests/test_phase5_closure.py::test_phase5_data_plane_closure_across_representative_evm_and_solana_chains` retains the Solana listener's own launch events (whose real transaction shape carries no address-identifying key the cohort rule recognizes) as a distinct, explicit `unresolved:` exclusion rather than collapsing them onto the resolved token. | PASS |

## Scope note: EVM reorg audit events are not loaded through `DatasetSnapshot`

`chain_reorg_detected` audit events are canonical-id-scoped to a synthetic
`{chain}:block:{number}` identity, not to a persisted asset. Composing them
into the same store that `DatasetSnapshot.from_duckdb` loads would trip its
existing unknown-asset-identity validation, which is a Phase 1/3 dataset
integrity guarantee this slice must preserve rather than weaken. The closure
test therefore proves EVM restart/reorg/gap-detection in an isolated store
(as ingestion-level evidence, matching the existing per-slice tests) and
carries only the resulting provider-quality outcome -- exactly what
`scheduler.pipeline.Pipeline.evm_listeners` itself records -- into the
composed research dataset. This is a scope boundary, not a defect: no
mandatory Slice 5.1-5.6 acceptance criterion requires reorg audit events to
be dataset-loadable, and no existing behavior was changed to make this
matrix pass. Making `chain_reorg_detected` (or other synthetic-identity audit
events) consumable by `DatasetSnapshot` remains an open item for a future
slice if a research use case needs it.

## External evidence kept separate

Credentialed live EVM RPC and Helius acceptance, and production-scale
longitudinal sample adequacy, remain **BLOCKED** on separately authorized
live ingestion runs. No Phase 5 result is represented as proof of live
data-plane reliability at production scale.
