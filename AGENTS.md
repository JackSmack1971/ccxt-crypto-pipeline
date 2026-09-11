# AGENTS.md

## Purpose and scope

This repository extends the completed Phase 1 crypto data-ingestion foundation through three sequential research and reporting phases:

- **Phase 2:** reproducible, point-in-time backtesting and strategy evaluation over local persisted data.
- **Phase 3:** falsifiable new-token alpha-discovery research built on Phase 2 temporal and replay guarantees.
- **Phase 4:** deterministic article and visualization generation from approved Phase 2–3 research artifacts.

The architecture MUST preserve these boundaries:

- Phase 1 ingestion remains the only layer allowed to call market, provider, explorer, RPC, or on-chain APIs.
- Phase 2, Phase 3, and Phase 4 MUST read local persisted inputs and MUST run without live provider access.
- Phase 2 owns simulation, execution timing, portfolio accounting, metrics, and result provenance.
- Phase 3 owns cohort construction, temporal features, labels, leakage controls, candidate evaluation, and research provenance.
- Phase 4 owns presentation of approved results and MUST NOT become a second analysis engine.
- Phase 4 generation is a review/presentation step only; it MUST NOT publish externally or make automated trading decisions.
- No phase authorizes live trading, paper trading, automated execution, paid data, or unsupported claims of predictive alpha.

## Instruction scope

This file is root repository guidance for Phases 2–4.

- A nested `AGENTS.md` SHOULD exist only when a subtree requires genuine exceptions or additional constraints; it MUST NOT duplicate this file.
- An `AGENTS.override.md` in a directory replaces `AGENTS.md` guidance for that same directory in Codex.
- More specific active user instructions and the active phase specification take precedence over broader repository guidance.
- When a phase-specific implementation contract is checked into the repository, use it together with the implemented code and tests; do not reconstruct missing requirements from memory.

## Sources of truth

Use these sources in this order:

1. The active user-provided goal or phase prompt defines the current checkpoint and allowed scope.
2. The checked-in phase design specification for the active phase, when present:
   - `phase-2-backtesting-strategy-framework.md`
   - `phase-3-new-token-alpha-discovery.md`
   - `phase-4-article-visualization-generation.md`
3. Existing code, tests, storage contracts, manifests, and configuration from completed phases define the implemented behavior that later phases MUST preserve.
4. The completed Phase 1 storage contract remains authoritative for canonical identities, ingestion-owned provider access, DuckDB/Parquet persistence, and migration/versioning behavior.

If repository evidence conflicts with a proposed design document, do not silently reconcile it. Report the conflict and preserve already-implemented contracts unless the active task explicitly authorizes a migration or behavioral change.

## Sequential phase execution

Phases 2, 3, and 4 MUST be implemented in order.

- Work only on the active phase or explicitly named implementation slice.
- NEVER implement deliverables that belong to a later phase merely because they are convenient.
- Preserve all acceptance criteria and architectural contracts established by completed phases.
- If the active phase exposes a defect in an earlier phase, make only the minimum compatible correction required for the active work and report it.
- Do not claim an acceptance criterion passed unless it was actually verified.
- If a required verification cannot run because an input artifact, dependency, environment capability, or other prerequisite is missing, report the criterion as blocked or unverified with the concrete reason.
- Open decisions in the phase specifications remain open until explicitly resolved; agents MUST NOT choose silently.

Before editing, inspect the repository for the implemented Phase 1 storage boundary, current analysis/reporting directories, tests, schema/versioning code, existing manifests, and configured test conventions.

## Phase-specific execution order

Within each phase, follow the design slices unless the active task narrows scope further.

### Phase 2

1. Freeze dataset snapshot and provenance contracts.
2. Add red tests for temporal joins and deterministic ordering.
3. Add read-only dataset loaders over the existing storage boundary.
4. Add the narrow strategy protocol and one trivial reference strategy.
5. Add the next-bar simulator and portfolio ledger.
6. Add metrics and manifest/result persistence.
7. Perform an independent look-ahead and accounting review before broadening strategy features.

### Phase 3

1. Freeze cohort, feature, label, split, and provenance schemas.
2. Build cohort extraction with complete inclusion/exclusion evidence.
3. Implement temporal joins and the feature registry.
4. Implement labels plus sealed discovery/evaluation splits.
5. Implement baselines, uncertainty, cost sensitivity, and candidate scoring.
6. Export a Phase 2-compatible strategy specification and human-readable research report.
7. Review for leakage and overfitting before broadening the feature set.

### Phase 4

1. Freeze approved-result manifest, claim-ledger, chart-spec, and package schemas.
2. Write validator fixtures/tests before renderer implementation.
3. Implement typed claim extraction and methodology/limitations generation.
4. Implement deterministic chart specifications and one static renderer.
5. Implement Markdown/HTML packaging only to the extent explicitly approved.
6. Add human-review, artifact, security, and accessibility checks.
7. Keep publishing, interactive dashboards, and model-assisted prose out of scope unless separately authorized.

## Repository map

The proposed Phase 2–4 design assigns these boundaries:

- `analysis/datasets/` — read-only, point-in-time snapshots over DuckDB/Parquet.
- `analysis/strategies/` — strategy protocol and strategy definitions that emit intentions, not fills.
- `analysis/backtesting/` — simulation clock, order lifecycle, execution assumptions, fees, slippage, cash, and positions.
- `analysis/metrics/` — metrics computed from the persisted simulator ledger.
- `analysis/runs/` — reproducible run manifests and immutable local result artifacts.
- `analysis/alpha/` — Phase 3 cohorts, temporal features, labels, splits, baselines, and candidate evaluation.
- `reporting/claims/` — validated claim extraction and claim-level provenance.
- `reporting/charts/` — declarative chart specifications.
- `reporting/render/` — deterministic rendering implementation.
- `reporting/package/` — article/package assembly, manifests, and review output.
- `config/` — versioned methodology or runtime configuration only after its contract is settled.
- `storage/` — existing canonical persistence boundary; any new persistent records MUST extend this boundary through the repository migration process.
- `tests/` — fixture, replay, leakage, accounting, renderer, security, accessibility, and end-to-end verification.

Do not create alternate data stores, provider-access paths inside analysis/reporting, or duplicate simulation/metric logic in Phase 3 or Phase 4.

## Environment and execution model

Analysis and reporting MUST be local-first and offline-capable.

- Phase 2–4 code MUST NOT call live market, explorer, RPC, provider, or on-chain APIs.
- Provider access remains an ingestion concern.
- Fixture acceptance paths MUST run with network access disabled.
- A local DuckDB + Parquet snapshot is the upstream data boundary unless an explicitly approved migration changes that contract.
- Secrets, secret-bearing URLs, and provider credentials MUST NOT appear in generated manifests, reports, charts, data exports, logs, or article packages.

The phase documents establish `python -m pytest` as the repository test command for these phases. Preserve it unless repository configuration proves that command has changed.

## Build and verification commands

Use the repository's established commands. For Phases 2–4, the design specifications explicitly require:

- `python -m pytest`

Phase-specific verification MUST additionally exercise the behaviors described below. Do not invent unverified CLI entry points.

When reporting completion, state the exact commands run and their outcomes. Distinguish unit/fixture evidence from end-to-end replay evidence.

## Shared temporal and provenance invariants

All Phase 2–4 outputs depend on point-in-time correctness and reproducibility.

- A value used for a decision MUST have an observation/effective timestamp no later than that decision timestamp.
- Unknown values remain unknown unless an explicit dataset policy authorizes a transformation.
- Forward-filling across token launch, metadata update, or other semantic boundaries is forbidden unless the dataset policy explicitly permits it.
- Later-discovered lineage MUST NOT leak into earlier launch-time features.
- Symbol text alone MUST NOT collapse or reconcile distinct asset identities when chain/address identity is required.
- EVM and Solana identities remain address-scoped and distinct.
- Every reproducible output MUST identify the exact dataset/snapshot, time range, relevant policy/config versions or hashes, and sufficient upstream lineage to reconstruct the result.
- Deterministic ordering MUST be defined anywhere unordered storage/query results could alter output.
- Same inputs plus same configuration MUST yield equivalent normalized outputs under the active phase's acceptance contract.

## Storage and schema boundaries

Phase 1 canonical storage remains authoritative.

- Analysis and reporting MUST treat raw Phase 1 persisted data as read-only.
- Raw ingestion rows MUST NEVER be rewritten merely to simplify a backtest, research cohort, label, or report.
- New persistent tables or fields require the repository storage migration procedure and a schema-version bump.
- Persisted additions MUST extend the canonical `storage/schema.py` / `storage/db.py` boundary when those files are the implemented migration/data-access contract.
- Do not create a separate database to bypass storage review.
- Result, cohort, feature, label, claim, or package records MAY remain file-based when the active design has not approved canonical database persistence.

Open persistence decisions MUST remain configurable or deferred until explicitly resolved.

## Phase 2 architecture and invariants

Phase 2 is a deterministic, bar-driven research simulator.

### Point-in-time datasets

`analysis/datasets/` MUST:

- construct read-only snapshots from local DuckDB/Parquet inputs;
- apply timestamp, source, lineage, and asset-eligibility rules;
- fail closed or return unavailable values when a feature/metadata observation occurs after the decision timestamp;
- expose deterministic ordering;
- preserve missingness rather than invent prices or metadata.

### Strategy boundary

`analysis/strategies/` MUST keep strategies separate from execution.

- Strategies return intentions such as target positions or orders.
- Strategies MUST NOT create fills, mutate cash, own holdings, apply fees, or decide slippage.
- Strategy outputs MUST be deterministic for the same point-in-time input and configuration.
- Analysis strategies MUST NOT import or call ingestion/provider adapters.

### Simulator boundary

`analysis/backtesting/` is the sole owner of:

- simulation clock;
- order validation and lifecycle;
- cash and position ledger;
- execution timing;
- rejected-order behavior;
- fees and slippage;
- missing/duplicate/halted/insufficient-bar policy;
- supported position constraints.

The first supported execution model is:

- signal observed at bar close;
- earliest execution at the next available bar open.

Do not add intrabar precision, leverage, shorting, live orders, optimization, or venue microstructure unless a later approved design explicitly introduces them.

### Metrics and manifests

- `analysis/metrics/` MUST compute metrics from the persisted or canonical simulator ledger, not from strategy internals.
- Every Phase 2 run MUST have a manifest containing dataset identity, query/policy version, time range, source filters, strategy/config identity or hash, simulator configuration, and code version where available.
- Fees and slippage MUST be visible in both ledger-level evidence and resulting metrics.
- Ambiguous asset identity, unavailable timestamps, or unsupported execution assumptions MUST produce an actionable rejection rather than an inferred result.

## Phase 2 testing requirements

Phase 2 verification MUST include:

- replaying the same fixture snapshot/configuration twice and comparing normalized trades, equity, metrics, and manifest inputs;
- a deliberately future-dated feature/metadata fixture proving look-ahead is blocked;
- a buy signal at bar `t` proving the documented next-bar execution rule;
- fee/slippage arithmetic checks;
- cash-conservation and position-limit checks where applicable;
- duplicate, missing, halted, or insufficient-bar fixtures with explicit outcomes;
- a complete fixture run with network access disabled;
- manifest and ledger inspection sufficient to reproduce the run.

If Phase 2 results become persistent tables, storage-schema review is required before considering the persistence work complete.

## Phase 3 architecture and invariants

Phase 3 produces a reproducible research dataset and candidate signal definitions. It does not produce an investment recommendation or automated trading decision.

### Cohort construction

- Define the cohort from reproducible persisted events such as `new_pool_detected` or Solana `token_mint_detected`.
- Each cohort definition MUST declare date range, chain set, event rule, and observation-quality threshold.
- "First seen" is an observation boundary, not proof of on-chain genesis.
- Every observed candidate MUST retain inclusion/exclusion status, event/source evidence, first-observed time, and exclusion reason when ineligible.
- Candidate discovery MUST be cohort-first, NEVER winner-first.

### Temporal feature registry

Every feature definition MUST declare:

- source columns/artifacts;
- effective timestamp;
- lookback;
- missing-value policy;
- allowed label horizon or temporal applicability.

Feature families SHOULD remain semantically separated between launch context, market behavior, structure/risk, and cross-source adoption.

Later CEX adoption or lineage is an outcome/label unless it was already known at the feature decision timestamp.

### Labels and splits

Every label MUST declare:

- horizon;
- censoring rule;
- quote currency;
- treatment of delisted or unavailable assets.

Discovery and evaluation MUST remain separate.

- Seal the held-out evaluation set before changing ranking rules in response to results.
- Candidate generation may explore many features, but held-out evaluation semantics MUST not shift silently.
- Unsupported or missing provider-derived risk capability MUST remain unavailable/uncertain rather than becoming a safe score.

### Candidate evaluation

Candidate reporting MUST include, where supported by the data:

- sample size and number of independent launches;
- coverage;
- missingness;
- horizon/censoring;
- baseline comparison;
- uncertainty or confidence bounds;
- turnover/cost sensitivity.

Baselines are compulsory where data supports them and SHOULD include no-trade, market/chain, age/liquidity, and simple momentum references.

A low-coverage result MUST NOT be presented as validated alpha.

## Phase 3 testing requirements

Phase 3 verification MUST include:

- deterministic replay of cohort rows, exclusions, features, labels, and candidate ranking;
- future-timestamp and late-lineage fixtures proving temporal exclusion;
- complete inclusion/exclusion and provenance evidence for every cohort member;
- a deliberately permuted-label or future-column leakage fixture that fails the leakage gate;
- EVM and Solana identity fixtures proving address-scoped joins and no symbol-only collapse;
- label tests for censoring, unavailable assets, and configured horizons;
- baseline/cost-sensitivity/uncertainty outputs where required by the selected methodology;
- export of at least one Phase 2-compatible strategy specification with unchanged temporal semantics;
- a handoff manifest identifying dataset, feature policy, labels, and evaluation split;
- offline execution using only persisted inputs.

Do not claim a candidate is profitable or production-ready merely because these tests pass.

## Phase 4 architecture and invariants

Phase 4 turns an approved research result into a reviewable article package. It is a presentation layer over approved Phase 2–3 artifacts.

### Approved-input boundary

- The generator MUST accept only an immutable, approved result/research manifest or equivalent approved local artifact.
- Phase 4 MUST NOT recompute labels, redefine cohorts, change simulator results, alter upstream costs, or replace unavailable values.
- Phase 4 MUST NOT import or call ingestion/provider adapters.

### Structured article model

Validate a structured article/claim/chart representation before rendering.

- Malformed or unsupported claims MUST fail validation.
- Every numeric or comparative factual claim MUST resolve to source result evidence.
- Unsupported narrative MUST be explicitly labeled interpretation or omitted.
- Methodology and limitations MUST be derived from the same approved manifest rather than authored from inconsistent side inputs.

### Claim ledger

Every factual claim MUST have enough provenance to resolve to the approved result, including as applicable:

- source result row/artifact;
- dataset/query/config hash or identity;
- time range;
- uncertainty or relevant limitation.

Unresolvable numeric claims MUST fail validation.

### Charts

Chart specifications MUST declare, as applicable:

- input data columns;
- only transformations already authorized by the upstream result contract;
- axis units;
- missing-data behavior;
- annotations;
- meaningful alt text;
- source attribution.

Charts MUST NOT fabricate zeros, labels, interpolation, or unsupported values.

Each rendered chart artifact MUST retain enough metadata for replay, including its specification, input manifest identity, renderer version, dimensions, accessibility text, and checksum.

### Package generation

The generated package SHOULD contain the approved output forms explicitly authorized by the active task, such as:

- article source and rendered output;
- chart specs and rendered images;
- sanitized tabular data where appropriate;
- claim ledger;
- methodology/limitations;
- validation results;
- renderer/code/config versions;
- output checksums;
- review report.

The generator creates a draft/review package only. Human review is a required gate before any external publication.

## Phase 4 testing requirements

Phase 4 verification MUST include:

- replaying generation from identical local inputs and comparing normalized article content, chart specs, and checksums;
- claim-ledger validation for every numeric claim;
- failure on unresolved claims;
- explicit handling of missing, empty, or unsupported chart values;
- chart checks for units, readable scales, source attribution, and meaningful alt text;
- the project's approved accessibility checks for rendered charts once the tool is selected;
- an end-to-end fixture package run with network access disabled;
- secret scanning and artifact inspection for API keys, RPC credentials, secret-bearing URLs, and unintended local paths;
- package inspection proving a reviewer can identify exact inputs, code/config versions, and validation results.

Do not invent an accessibility tool, renderer, or publication format while those design choices remain unresolved.

## Change boundaries

Across Phases 2–4:

- NEVER add live trading, paper trading, automated execution, or strategy optimization without a new approved design.
- NEVER add paid data/provider dependencies to make research or reporting work.
- NEVER move external API access into analysis or reporting.
- NEVER rewrite Phase 1 raw rows for research convenience.
- NEVER collapse distinct asset identities from symbol text alone.
- NEVER present unsupported provider capability as a safe/default value.
- NEVER let Phase 4 recompute upstream research semantics.
- NEVER claim predictive alpha, profitability, or production readiness from a methodology/fixture pass.
- NEVER add external publishing or social distribution from Phase 4 without explicit authorization.

## Security and external systems

- Real credentials MUST NOT be committed.
- Secrets MUST NOT be logged or embedded in manifests, reports, article text, chart data, image metadata, complete URLs, or generated packages.
- Offline analysis/reporting tests SHOULD disable network access where practical and MUST do so where required by the phase acceptance path.
- Generated output MUST avoid leaking unintended local filesystem paths.
- Provider capability uncertainty from Phase 1 remains explicit downstream; reporting MUST preserve unsupported/unavailable states rather than laundering them into certainty.

## Documentation requirements

Documentation MUST describe implemented behavior, not aspirational architecture.

- Keep detailed methodology, runbooks, schema references, and API/provider material in dedicated files and reference them from this guidance.
- When an open decision is resolved, update the authoritative phase/config documentation and tests rather than encoding an undocumented choice only in code.
- Phase handoff documentation MUST identify unresolved decisions and blocked criteria.

## Completion criteria

An active Phase 2–4 implementation slice is complete only when:

- Its required deliverables exist and stay within the active phase/slice scope.
- Relevant `python -m pytest` coverage passes, or blocked verification is reported precisely.
- Required offline/replay checks for that slice have actually been exercised.
- Earlier phase contracts still hold.
- No later-phase implementation was pulled forward.
- New persistence, if any, followed the storage migration/versioning contract.
- Point-in-time and identity semantics remain intact.
- Generated or persisted artifacts contain sufficient provenance for their phase contract.
- No secret, live-provider dependency, paid-data dependency, unsupported inferred value, or architectural bypass was introduced.
- The completion report identifies changed files, verification commands and outcomes, replay/end-to-end checks performed, and unresolved blockers.
- Phase 2 completion does not imply alpha discovery or live trading.
- Phase 3 completion does not imply validated profitability or production readiness.
- Phase 4 completion does not imply publication approval; human review remains the final gate.
