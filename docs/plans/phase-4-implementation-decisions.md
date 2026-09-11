# Phase 4 implementation decisions

These decisions resolve the open choices in
`phase-4-article-visualization-generation.md` for the first local delivery
slice:

- Output is Markdown article source plus static SVG charts. HTML/PDF are not
  required by the repository requirements and remain deferred.
- The renderer is a small standard-library SVG renderer. Accessibility is
  checked by the repository-owned validator for `role=img`, title, description,
  units, source attribution, and explicit missing-data state.
- Input and output are file-based. The caller supplies the output directory;
  generated packages are not written to Phase 1 storage or committed as runtime
  state.
- Human approval is represented by a retained `review.json` with
  `status: pending` and `approval_required: true`. Generation never changes
  this status or publishes a package.
- Approved input `staged_tables` entries contain a relative `path` and SHA-256
  `sha256`; generation verifies the bytes before resolving claims or rendering.
  Numeric claim evidence must match the approved dataset, query/config identity,
  and time range exactly.
- Approved input also carries explicit `approval.status: approved` metadata,
  a hash-verified Phase 3 `research_run`, and linked Phase 3 artifact hashes.
  Generation rejects missing or mismatched research lineage before rendering.

The implementation intentionally has no ingestion/provider imports and uses no
generative-model or charting dependency.

The cross-phase acceptance test
`tests/test_phase4.py::test_phase3_artifact_is_accepted_only_through_explicit_approved_handoff`
uses the actual Phase 3 artifact writer output, verifies its manifest and
artifact hashes, and records the linked research run in the generated package.
The end-to-end fixture
`tests/test_phase4.py::test_offline_phase1_to_phase4_chain_is_content_addressed_and_review_gated`
extends that proof from persisted Phase 1 DuckDB input through Phase 3 labels
and the Phase 4 pending-review package with network access denied.
