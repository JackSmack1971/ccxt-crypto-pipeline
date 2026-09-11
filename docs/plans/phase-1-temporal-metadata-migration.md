# Phase 1 temporal metadata and lineage migration

**Status:** Implemented

Phase 1 metadata, cross-source lineage, and OHLCV are now observation histories
rather than current-state upserts. Metadata uses `(canonical_id, last_updated)`,
lineage uses `(dex_canonical_id, cex_canonical_id, linked_at)`, and OHLCV uses
`(canonical_id, timestamp, timeframe, source)`, allowing analysis to select only
evidence known at a point in time without overwriting earlier observations.

## Migration contract

- `SCHEMA_VERSION` advances from 2 to 5.
- Existing `metadata` rows are copied transactionally into the target table,
  then the replacement is renamed into place.
- Re-running initialization is idempotent.
- `upsert_metadata` remains idempotent for the same asset and observation time,
  while distinct observation times are preserved.
- Lineage reconciliation remains idempotent for the same link and observation
  time, while later discovery timestamps are preserved.
- OHLCV writes remain idempotent for the same source-scoped bar, while distinct
  source observations are preserved.
- No Parquet layout or provider boundary changes.

## Verification

- `tests/test_storage.py::test_v1_store_migrates_in_place_and_preserves_rows`
  verifies prior-schema upgrade and row preservation.
- `tests/test_storage.py::test_metadata_observations_preserve_point_in_time_history_and_are_idempotent`
  verifies historical observations and same-timestamp idempotence.
- `tests/test_storage.py::test_lineage_observations_preserve_point_in_time_history_and_are_idempotent`
  verifies historical links and same-time reconciliation idempotence.
- `tests/test_phase2.py::test_multi_source_bars_are_preserved_and_unambiguous_selection_is_required`
  verifies source-scoped OHLCV preservation and fail-closed dataset selection.
- `DatasetSnapshot.metadata_at()` selects the latest observation at or before
  the decision time; Phase 2 and Phase 3 callers consume this read-only view.
- `storage_migration_guard.py` confirms the version advance and accessor change.
- `uv run python -m pytest` passes the complete fixture suite.

This migration improves temporal completeness of locally collected metadata and
lineage; it does not establish that upstream provider observations are complete
or prove on-chain genesis timing.
