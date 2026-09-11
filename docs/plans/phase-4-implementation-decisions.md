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

The implementation intentionally has no ingestion/provider imports and uses no
generative-model or charting dependency.
