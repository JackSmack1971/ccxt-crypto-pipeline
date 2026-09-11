# Phase 4 design pass: article and visualization generation

**Status:** Local kernel and approved-research handoff implemented; publication and richer formats remain deferred
**Date:** 2026-09-09
**Depends on:** Phase 2 reproducible results and Phase 3 provenance-rich research
artifacts

## Goal

Turn an approved research result into a reviewable article package with accurate,
accessible visualizations and claim-level provenance. Generation must be a
deterministic presentation step over local artifacts, not a second analysis engine
or a path to live-provider access.

## Constraints and facts

- Phase 1 is local-only and analysis layers must read persisted data.
- Phase 2 owns simulation, metrics, and result semantics; Phase 3 owns cohort,
  feature, label, and discovery provenance.
- Generated prose and charts are potentially misleading if they hide missingness,
  selection rules, costs, or uncertainty.
- Secrets, complete secret-bearing URLs, and unsupported provider values must never
  enter generated artifacts.

## Proposed architecture

```text
approved result manifest + research tables
                 |
                 v
          claim extraction/validation
                 |
       typed article model + chart specs
          |                    |
          v                    v
    Markdown/HTML draft     PNG/SVG/data
          \                    /
           -> package manifest + review report
```

The generator should accept only an immutable, approved manifest and produce a
versioned package containing:

- article source and rendered output;
- chart specifications plus rendered images and, where appropriate, sanitized
  tabular data;
- a claim ledger mapping every numeric or comparative statement to source result
  rows, query/config hashes, time range, and uncertainty;
- a limitations/methodology section generated from the same manifest;
- validation results, renderer versions, and output checksums.

Templates should be declarative and deterministic. A visualization spec should
declare data columns, transformations already authorized by the result contract,
axis units, missing-data behavior, annotations, alt text, and source citation.
Article generation may summarize approved metrics but may not recompute labels,
change cohorts, or silently replace unavailable data.

## Design decisions

1. **Structured intermediate representation first.** Validate an article model and
   chart specs before rendering text or images; malformed claims fail the run.
2. **Claim-level evidence is mandatory.** Every factual claim has a source pointer;
   unsupported narrative is labeled interpretation or omitted.
3. **Charts are reproducible artifacts.** Store spec, input manifest, renderer
   version, dimensions, accessibility text, and checksum with each output.
4. **Human review is a gate.** The generator creates a draft/review package; it
   does not publish externally or represent generated interpretation as fact.
5. **No direct ingestion dependency.** The package must run with network disabled
   after its local inputs are staged.

## Alternatives considered

### Free-form LLM article generation from database rows

Low initial effort but weak traceability and high risk of invented claims or omitted
limitations. Rejected as the system contract; a language model may be an optional
drafting aid behind the validated claim ledger later.

### Notebook-only charts and prose

Useful for exploration but difficult to replay, review, and package consistently.
Notebooks may remain an authoring interface, while the durable output contract is
the manifest-driven package.

### Dashboard as the first deliverable

Interactive dashboards add hosting, state, and deployment concerns that are not
needed for a local research artifact. Deferred until static package quality is
proven.

## Acceptance criteria

1. Given an approved result manifest and identical local inputs, generation produces
   identical normalized article content, chart specs, and checksums.
2. Every numeric claim in the article has a claim-ledger entry resolving to an
   approved result and configuration; unresolvable claims fail validation.
3. The generated package states cohort/split, time range, costs, missingness,
   uncertainty, and limitations without changing the upstream result.
4. A chart with missing, empty, or unsupported values renders an explicit state or
   fails with a useful error; it never displays fabricated zeros or labels.
5. Each chart has units, readable scales, source attribution, and meaningful alt
   text; rendered output passes the project’s chosen accessibility checks.
6. With network access disabled and a fixture package staged, generation succeeds
   without importing or calling ingestion/provider adapters.
7. Secret-scanning and artifact inspection show no API keys, RPC credentials,
   secret-bearing URLs, or unintended local paths in prose, chart data, or manifests.
8. A human reviewer can identify the exact inputs, code/config versions, and
   validation results from the package alone.

## Implementation slices and handoff

1. Freeze the approved-result manifest, claim ledger, chart-spec, and package
   schemas; decide whether these are files only or also canonical storage records.
2. Build fixture result packages containing normal, empty, uncertain, and rejected
   claims; write validator tests before renderers.
3. Implement typed claim extraction and limitations/methodology sections; test
   missing provenance, stale manifests, and secret-bearing strings.
4. Implement deterministic chart specifications and one static renderer; test
   units, missing values, alt text, and checksum replay.
5. Implement Markdown/HTML packaging and an offline end-to-end test.
6. Add human-review output and artifact/security/accessibility checks; do not add
   publishing or live data access in the first slice.

Natural handoff: an offline, reviewable package format and renderer acceptance
matrix. Publication, interactive dashboards, and model-assisted prose require a
new design decision.

## Planned repository surface and verification

Expected new paths are `reporting/claims/`, `reporting/charts/`,
`reporting/render/`, `reporting/package/`, and focused tests under `tests/`.
Generated packages should live in an explicitly configured local output directory,
not in the Phase 1 storage tables unless a separate persistence decision approves
that extension. Verification uses the existing `python -m pytest` command, an
offline fixture-package run, repeated-output checksum comparison, accessibility
checks for rendered charts, and a secret/artifact scan.

## Deferred decisions after the first local delivery

- HTML/PDF and interactive output are not part of the first local delivery.
- The standard-library SVG renderer and repository-owned accessibility checks are
  the supported first-delivery path.
- Generated packages remain caller-supplied, file-based, and pending human
  review; external publication is not authorized.

## Phase boundary

This plan does not authorize publishing, social distribution, automated
recommendations, or a generative model dependency. It defines a local, evidence-
linked presentation layer over approved Phase 2–3 outputs.
