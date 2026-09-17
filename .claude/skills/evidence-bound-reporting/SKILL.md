---
name: evidence-bound-reporting
description: >-
  Implements, modifies, and debugs a repository's Phase 4 evidence-bound reporting
  boundary: approved-research handoffs, factual claim/derivation validation, chart
  specifications or transformations, deterministic rendering, accessibility and
  provenance checks, and review-package generation. Use when reporting output must
  remain provably derived from immutable approved local research. Do not use for
  Phase 3 cohort/feature/label/statistical methodology, Phase 2 backtest semantics,
  ingestion/provider work, storage-schema migrations, free-form editorial writing,
  or external publication/distribution.
---

# Evidence-Bound Reporting

Build or repair the local reporting layer so every emitted factual result remains traceable to immutable approved research, deterministic under replay, review-gated, and unable to silently change upstream semantics.

## Authority and progressive loading

1. Read the active user goal, every applicable `CLAUDE.md`, then any repository-declared cross-tool instruction chain such as `AGENTS.md` / `AGENTS.override.md`, plus `ROADMAP.md`, the active Phase 4 plan/decision document, and the relevant reporting code/tests before editing.
2. Treat live repository code, tests, manifests, schemas, and current plans as authoritative over this package's snapshots. Never copy a mutable field list, version, hash, or schema value from this skill without confirming it in the repository.
3. Read `references/repository-contract.md` to locate the reporting authorities and neighboring workflow boundaries.
4. Read `references/derivation-model.md` when the task changes factual claims, numeric/comparative values, chart transformations, units, formatting, annotations, or missing-value semantics.
5. Read `references/verification-matrix.md` when selecting tests, validating generated packages, or handling blocked/inconclusive evidence.
6. Use `python <skill-dir>/scripts/reporting_guard.py --repo <repo-root>` after reporting code changes. Add `--package <generated-package>` when a package can be generated safely. Run `python <skill-dir>/scripts/self_test.py` after modifying this skill package.

## Routing boundary

This workflow owns changes whose correctness depends on preserving the chain:

**approved immutable research -> declared evidence/derivation -> validated claim/chart model -> deterministic render -> immutable review package**.

Use a neighboring workflow instead when the task changes:

- provider acquisition or normalization -> ingestion workflow;
- persisted DuckDB/Parquet contract -> storage migration workflow;
- simulator timing/accounting/metrics semantics -> backtest-integrity workflow;
- cohorts, features, labels, splits, hypotheses, statistical promotion, or robustness methodology -> research-governance workflow;
- publication, posting, deployment, or distribution -> separately authorized external-effects workflow.

A reporting task may consume upstream artifacts; it must not redefine them.

## Mandatory decision model

### Input and approval boundary

- Consume only the repository-approved Phase 3 -> Phase 4 handoff or its explicitly authorized successor. Do not invent an alternate bypass manifest because an input is inconvenient.
- Verify referenced research manifests and staged/reportable artifacts by repository-defined identity/hash rules before resolving claims or rendering charts.
- Preserve the upstream research run byte-for-byte. Reporting may stage/copy approved artifacts but must not mutate the source research run.
- Require explicit approval metadata before generation when the repository contract requires approval. Generation must not convert an approved input into publication approval; the output remains review-gated.
- Reject unknown, ambiguous, mismatched, or unverifiable lineage rather than guessing the intended dataset, configuration, time range, row, field, or approval scope.

### Evidence-derived factual claims

For every factual numeric or comparative claim affected by the task:

- Make the value a result of a declared, machine-checkable derivation from approved staged evidence. A pointer to an artifact/row is not sufficient when the emitted value itself can disagree with that evidence.
- Bind the derivation to the exact source artifact and source location/field(s), the operation semantics, unit semantics, missing/unavailable behavior, and output formatting needed to reproduce the emitted value.
- Validate the derived value before article/package rendering. The renderer must consume validated output rather than independently recomputing research semantics.
- Keep interpretation distinct from fact. Interpretation may not introduce undeclared numeric/comparative facts.
- Fail closed on unsupported operations, incompatible units, absent source values, ambiguous multiple matches, or a rendered value that differs from the validated derivation beyond an explicitly declared formatting/rounding rule.
- Preserve upstream uncertainty, censoring, coverage, missingness, limitations, and unsupported states when they are material to the claim. Do not launder them into certainty.

Do not assume a particular derivation schema or operation whitelist from this skill. Confirm the repository's implemented contract. If the active task introduces one, define only the operations needed by the authorized scope and test each operation independently.

### Chart semantics

For every affected chart:

- Require a declarative chart specification before rendering.
- Bind data columns to approved staged artifacts and make units explicit.
- Permit only transformations explicitly authorized by the repository's reporting contract. Reject unknown transformations; never treat an unimplemented transform as a no-op.
- Execute declared annotations deterministically or reject them. Never silently ignore a declared annotation.
- Preserve missing/unsupported values according to the declared missing-data policy. Never fabricate zero, interpolate, drop, or relabel unavailable data unless that exact behavior is authorized and represented in provenance.
- Keep transformation/annotation semantics in package provenance sufficient for replay.
- Require meaningful alt text, source attribution, readable dimensions/scales, and the repository-approved structural accessibility checks.

### Determinism, packaging, and review

- Same approved inputs + same reporting configuration/code contract must yield equivalent normalized article content, claim/derivation records, chart specs, rendered artifacts, and checksums under the repository acceptance definition.
- Keep analysis/reporting offline-capable. Reporting code must not import or call ingestion/provider clients or introduce network-dependent acceptance tests.
- Keep generated outputs in caller-supplied/local artifact locations unless an explicitly approved persistence migration changes that boundary.
- Preserve immutable-package behavior: an existing artifact with the same identity but different bytes is a conflict, not permission to overwrite history.
- Retain exact input identities, relevant code/config identities, validation results, artifact checksums, and pending human-review state in the package contract.
- Scan emitted artifacts for credentials, secret-bearing URLs, and unintended local filesystem paths.

## Prohibited

- Recompute Phase 2 metrics, Phase 3 labels, cohorts, splits, candidate states, statistical tests, or research approval inside reporting.
- Import/call live provider, exchange, explorer, RPC, or on-chain clients from reporting code.
- Resolve a missing or unsupported research value by substituting zero, parity, a default metric, a later observation, or a model-generated guess.
- Let free-form prose become the source of truth for a numeric/comparative fact.
- Silently accept unknown derivation operations, chart transformations, annotations, units, claim kinds, or manifest fields where the repository contract is strict.
- Weaken hash, approval, offline, secret, accessibility, determinism, or human-review gates to make a package generate.
- Add publication, social distribution, remote upload, live dashboards, or model-assisted prose unless the active task explicitly authorizes a new boundary and its consequences.

## Judgment regions

Use judgment only where the repository has not fixed semantics. Select the narrowest option that preserves traceability and can be disproved by tests.

- **Derivation representation:** choose a typed structure that makes source, operation, units, and formatting independently inspectable; do not optimize for terse prose.
- **Formatting/rounding:** choose presentation rules only after underlying numeric semantics are fixed. Formatting may change representation, never source meaning.
- **Chart transform design:** prefer explicit small operations over opaque arbitrary expressions. Add only what the current reporting need requires.
- **Validation breadth:** run focused tests first, then every repository-required gate and the smallest broader replay/offline/security checks capable of detecting cross-boundary regressions.
- **Compatibility:** preserve an existing accepted manifest/package contract when possible. If correctness requires a versioned breaking change, make the version boundary explicit rather than silently reinterpreting old artifacts.

## Workflow

### 1. Reconcile the live contract before editing

Inspect at minimum the active reporting plan/decisions, `reporting/claims/`, `reporting/charts/`, `reporting/render/`, `reporting/package/`, `tests/test_phase4.py`, and any upstream artifact type directly consumed by the change.

Write down for the active slice:

- exact approved input contract;
- factual output(s) whose correctness can change;
- derivation/transform semantics required;
- forbidden upstream recomputation;
- package/review/security invariants;
- observable tests that would fail if the implementation were subtly wrong.

If the requested behavior conflicts with an upstream research contract, stop and surface the conflict. Do not repair a Phase 3 decision inside Phase 4.

### 2. Freeze semantics before renderer behavior

For claim changes, define the typed derivation contract and validator behavior before modifying prose rendering.

For chart changes, define/extend spec validation, allowed transforms, missing-value semantics, annotations, units, and provenance before renderer behavior.

For package/handoff changes, define strict input/output fields, version compatibility, immutable identity, and failure behavior before writing files.

Prefer red tests at the validation boundary before renderer/package implementation when the failure is deterministic and locally expressible.

### 3. Implement fail-closed validation

Validation must be capable of disproving success. Cover both the accepted path and the most plausible dangerous mismatch:

- claim text/value disagrees with evidence/derivation;
- source row/field is absent or ambiguous;
- operation or unit is unsupported;
- transform is unsupported;
- annotation is declared but cannot be executed;
- missing value would otherwise become zero/disappear;
- input hash/approval/research lineage is invalid;
- package would contain a secret or local path;
- reporting attempts network/provider access.

Do not add a permissive fallback merely to preserve rendering.

### 4. Render only validated structures

Keep rendering mechanically downstream of validation. A renderer may format or visualize the validated result; it must not decide new research semantics.

When a requested visual/report behavior cannot be represented by the approved typed contract, extend the contract or stop blocked. Do not smuggle extra logic into the renderer.

### 5. Verify through independent evidence

Run all applicable evidence from `references/verification-matrix.md`.

At minimum for a behavioral reporting change:

1. focused validator/renderer/package tests;
2. mismatch/fail-closed tests for the changed semantic branch;
3. deterministic replay of the affected artifact/package path;
4. offline/network-denial evidence for reporting;
5. `reporting_guard.py --repo ...`, plus `--package ...` when available;
6. repository-required broader tests/CI gates for the slice;
7. final artifact inspection for review state, checksums, secrets/paths, and unintended files.

A passing unit test is not sufficient if the task changes emitted artifacts but no generated artifact was inspected.

### 6. Stop at the evidence boundary

Declare completion only for the reporting slice actually proven. Do not infer research validity, profitability, publication approval, or production readiness from a valid report package.

## Failure branches

| Divergence | Required response |
|---|---|
| Approved handoff/research hash mismatch | Reject before claim resolution/rendering; do not repair or restage unknown bytes silently. |
| Claim source exists but emitted number does not derive from it | Fail validation; fix derivation/format logic or the claim declaration, not the upstream result. |
| Derivation operation/unit semantics are undefined | Stop `BLOCKED` until the reporting contract defines them; do not infer arithmetic semantics. |
| Missing/unsupported evidence value | Preserve explicit unavailable state or fail according to the declared contract; never invent zero/default. |
| Unsupported chart transformation | Reject the spec; implement and test only if the active task authorizes that transform. |
| Declared annotation cannot be executed | Reject rather than silently omit it. |
| Accessibility check/tool unavailable | Run repository-owned deterministic checks that exist; report any additionally required external check as `UNVERIFIED`, never `PASS`. |
| Network/provider dependency appears in reporting | Remove it or stop; reporting acceptance remains local/offline. |
| Generated artifact contains secret/path evidence | Fail generation/validation and remove the leak from the reporting path; do not redact only the final review summary while leaving the artifact unsafe. |
| Existing immutable package identity has different bytes | Treat as conflict; do not overwrite. Fix identity inputs/versioning or choose the repository-authorized new package path. |
| Upstream research semantics appear wrong | Report the upstream issue and stop at the Phase 4 boundary unless the active user task separately authorizes upstream work. |
| Required package/replay test cannot run | Report `BLOCKED`/`UNVERIFIED` according to repository policy; do not substitute code inspection for required runtime evidence. |
| External publication/upload is requested incidentally | Stop at review-package completion and require explicit authorization for the external action. |

## Completion contract

A reporting slice is complete only when all applicable conditions are observed:

- the accepted input is immutable, approved, and hash/identity verified under the live repository contract;
- affected factual numeric/comparative output is validated as a declared derivation of approved evidence, not merely linked to it;
- affected charts use only allowed, executed transformations/annotations and preserve explicit missing-value semantics;
- renderer/package output is deterministic under the repository replay definition;
- reporting remains offline and does not introduce provider/ingestion coupling;
- output retains provenance, checksums, review-required state, and relevant code/config/input identities;
- accessibility checks required by the repository pass for affected rendered charts;
- secret/local-path inspection passes;
- focused and repository-required broader tests pass, with pre-existing failures distinguished from introduced failures;
- no upstream research semantics or external publication state changed without separate authorization.

If any required evidence is absent or inconclusive, do not call the slice complete.
