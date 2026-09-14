# Engineering Roadmap

**Status:** Active execution authority for forward work  
**Current phase:** Phase 4 completion and integrity reconciliation  
**Baseline:** `main` at `d5041339688e25a81d2c0344754f1a2a58bd60a1`  
**Last reconciled:** 2026-09-11

This file is the durable forward roadmap for `ccxt-crypto-pipeline`. It exists so a new agent can determine the repository's actual execution frontier without reconstructing intent from chat history, stale phase prose, or commit messages.

Read `AGENTS.md` first for repository-wide constraints, then read this file before selecting work. Phase design documents under `docs/plans/` remain authoritative for their local contracts. Existing code, tests, schemas, manifests, and configuration remain authoritative for behavior that has already landed.

If this roadmap conflicts with executable repository evidence, **do not silently follow the roadmap**. Treat the implementation conflict as a roadmap-reconciliation task, preserve already-landed contracts unless explicitly authorized to migrate them, and update this document in the same change that resolves the discrepancy.

---

## 1. Operating model

### 1.1 How agents select work

Unless the active user request names a different target:

1. Read `AGENTS.md`, this `ROADMAP.md`, and the active phase plan.
2. Inspect `main`, tests, schemas, manifests, Git status, and recent commits sufficiently to confirm the roadmap still matches reality.
3. Select the **first incomplete, unblocked slice** in the active phase.
4. Advance **exactly one smallest coherent, independently verifiable slice**.
5. Add or update adjacent tests before claiming completion.
6. Run the narrowest relevant verification plus the repository-wide gates required by the slice.
7. Update this roadmap's status/evidence only when the implementation and verification have actually landed.
8. Stop for review rather than pulling later slices forward.

A slice is not complete because code exists. It is complete only when its exit criteria are satisfied by repository evidence.

### 1.2 Status vocabulary

Use only these statuses in this document:

- **DONE** — landed on `main` and verified against the listed exit criteria.
- **ACTIVE** — current implementation frontier.
- **PLANNED** — sequenced but not yet started.
- **BLOCKED** — cannot safely proceed; the blocker must be stated explicitly.
- **DEFERRED** — intentionally outside the current product boundary.

### 1.3 Slice discipline

Each implementation slice SHOULD:

- preserve phase boundaries and offline analysis/reporting guarantees;
- avoid speculative abstractions and unrelated refactors;
- define observable acceptance criteria before implementation;
- keep migrations backward-safe and idempotent;
- fail closed on ambiguous identity, time, provenance, source, quote currency, or approval state;
- preserve missingness/unsupported states instead of laundering them into defaults;
- produce deterministic artifacts when the phase contract requires replay;
- leave no undocumented semantic decision encoded only in code;
- be reviewable as a single coherent pull request whenever practical.

### 1.4 Universal merge gates

Every slice must satisfy the gates that apply to it:

- `python -m pytest` (or `uv run python -m pytest` when using the locked environment);
- focused tests for the changed boundary;
- offline/network-denial tests for Phase 2–4 paths that must not contact providers;
- storage migration guard when `storage/` schema/accessor contracts change;
- deterministic replay checks for artifact-producing code;
- secret/path inspection for manifests, reports, charts, and package output;
- `git diff --check` or equivalent whitespace validation;
- no unresolved regression in an earlier phase contract.

Green CI evidence is mandatory for Phase 4R.2 and every later slice.

---

## 2. Current repository baseline

The repository has moved beyond its original phase prose. The current baseline includes:

- **Phase 1 ingestion/storage:** CEX, Tier-0 DEX, EVM, Solana, normalization, scheduling, DuckDB/Parquet persistence, schema version 5, timestamped metadata/lineage observations, and source-scoped OHLCV.
- **Phase 2 backtesting:** read-only point-in-time snapshots, a narrow strategy protocol, deterministic single-CEX next-bar-open simulation, fees/slippage, metrics, and immutable run artifacts.
- **Phase 3 research:** cohort extraction, temporal feature registry, fixed-horizon labels, purged chronological discovery/validation/holdout partitions, governed candidate-promotion states, multiple-testing helpers, deterministic research artifacts, and Phase-2-compatible handoff metadata.
- **Phase 4 reporting:** hash-verified Phase 3 linkage, hash-verified staged inputs, claim/chart validation, deterministic SVG rendering, Markdown package generation, secret checks, immutable package artifacts, and a pending human-review gate.
- **Cross-phase evidence:** the test suite includes an offline, content-addressed Phase 1 → Phase 3 → approved Phase 4 fixture chain.
- **Continuous verification:** GitHub Actions runs the locked fixture/unit suite, storage migration guard, byte-compilation, and whitespace checks for pull requests and `main` without provider credentials.

The latest hardening work fixed several earlier weaknesses: metadata/lineage history is retained by observation time, OHLCV is source-scoped, ambiguous source selection fails closed, Phase 3 run identity commits to artifact hashes, and Phase 4 verifies linked research/staged content hashes.

### 2.1 What is *not* yet proven complete

The following remain open and define the active frontier:

- short-horizon real-data coverage for new DEX/on-chain assets is not yet a production ingestion contract comparable to the synthetic 1h fixtures;
- token/pool/market identity semantics still need a production-grade contract where provider events describe pools but research evaluates token-level outcomes;
- quote-to-USD semantics are not yet a durable historical conversion contract for non-USD quote assets;
- Phase 2 portfolio metrics need timestamp-level aggregation/frequency-aware annualization before broader multi-asset research use;
- Phase 4 claim validation proves provenance linkage but does not yet prove that a number stated in prose is a declared derivation of the referenced evidence value;

These gaps are why the project is considered **in Phase 4, but not yet Phase 4-complete**.

---

# Phase 4R — Completion & Integrity Reconciliation

**Status:** ACTIVE  
**Goal:** Close the trust chain across Phases 1–4 before expanding product surface.  
**Exit condition:** A production-shaped local dataset can move through point-in-time research, statistically governed candidate evaluation, explicit approval, and deterministic reporting with every identity, timestamp, derivation, input, and decision traceable and replayable.

Do not add publishing, live/paper trading, strategy optimization, paid-data fallbacks, dashboards, or model-generated prose during Phase 4R.

## Slice 4R.1 — Continuous verification and merge evidence

**Status:** DONE

Establish repository-native CI before additional behavioral expansion.

Deliverables:

- a minimal GitHub Actions workflow for the locked Python environment;
- repository-wide tests on pull requests and `main`;
- storage migration guard execution when relevant;
- deterministic/static checks that are already part of local completion practice;
- dependency caching only if it does not weaken reproducibility.

Acceptance:

- a clean checkout can execute the documented verification without local-only assumptions;
- CI fails on a deliberately failing test in validation of the workflow itself;
- no secrets are required for fixture/unit CI;
- provider/live acceptance remains explicitly separate from fixture CI.

Exit gate: later slices SHOULD NOT be marked DONE without green CI evidence after this lands.

Evidence:

- `.github/workflows/ci.yml` installs the project from `uv.lock`, pins the test runner, and runs on pull requests and pushes to `main` with read-only repository permissions.
- `tests/test_ci.py` guards workflow triggers, locked installation, required repository checks, and the absence of live/provider credentials or commands.
- The workflow runs the complete fixture/unit suite, the version-1 storage migration fixture, byte-compilation, and `git diff --check`; a temporary failing test confirmed that pytest failures propagate as a nonzero status.
- Hosted CI remains the merge-time evidence for each pull request; fixture CI does not claim live-provider acceptance.

## Slice 4R.2 — Real purge/embargo split semantics

**Status:** DONE

Make the Phase 3 chronological split enforce what the report says it enforces.

Deliverables:

- explicit temporal boundary representation for discovery, validation, and sealed holdout;
- purge/embargo logic that excludes observations whose feature/label windows overlap protected boundaries;
- deterministic evidence of which rows were removed and why;
- report/manifests generated from actual split semantics rather than fixed prose.

Acceptance:

- boundary fixtures demonstrate leakage-prone rows are excluded;
- changing `embargo_days` changes the selected rows, not just metadata;
- sealed holdout membership cannot be altered by downstream ranking logic;
- repeated split construction is byte/structurally deterministic.

Evidence:

- `analysis/alpha/evaluation.py` fixes the raw chronological boundaries before applying label-window purge, feature-window purge, and post-boundary embargo rules; its result retains boundary and row-removal evidence.
- `analysis/alpha/report.py` describes the supplied split's actual window configuration and removal count instead of fixed prose.
- `tests/test_phase3.py` covers boundary overlap, an effective embargo change, sealed holdout membership, removal reasons, and structurally deterministic replay.

## Slice 4R.3 — Candidate promotion state machine

**Status:** DONE

Replace the current coverage-only `validated_alpha` shortcut with explicit research states.

Minimum states:

`discovered -> discovery_promoted -> validation_confirmed -> holdout_confirmed`

with explicit terminal states such as `rejected`, `insufficient_coverage`, and `insufficient_evidence`.

Promotion MUST require declared evidence appropriate to the stage, including:

- minimum independent sample and coverage requirements;
- corrected discovery significance (BH/FDR where configured);
- validation replication under frozen semantics;
- sealed holdout confirmation with Holm or the active confirmation policy;
- baseline comparison;
- uncertainty/effect-size evidence;
- configured cost sensitivity.

Acceptance:

- no helper can emit a validated/confirmed state solely from coverage;
- failing any mandatory gate produces an explicit non-promoted reason;
- the hypothesis registry and candidate artifact preserve all promotion inputs and decisions;
- tests cover false-positive prevention and successful promotion.

Evidence:

- `analysis/alpha/evaluation.py` defines versioned promotion policy/evidence/decision records and enforces sequential discovery, validation, and sealed-holdout gates with explicit terminal reasons.
- Candidate results can report validated status only after `holdout_confirmed`; ranking uses governed states rather than the former coverage-derived boolean.
- The hypothesis registry and content-addressed research artifacts retain candidate statistics, policy, submitted evidence, decisions, and rejection reasons.
- `tests/test_phase3.py` covers coverage-only false-positive prevention, each successful state transition, a mandatory-gate rejection, and persisted promotion evidence.

## Slice 4R.4 — Quote-currency and USD conversion provenance

**Status:** DONE

Make forward-return labels economically explicit for non-USD quote assets.

Deliverables:

- quote-asset identity available to the label boundary;
- versioned conversion policy;
- historical conversion observation identity/timestamp/source when conversion is required;
- explicit stablecoin treatment rather than implicit parity;
- fail-closed behavior when conversion evidence is unavailable.

Acceptance:

- a non-USD/non-approved-stable quote cannot silently use `1.0` conversion;
- conversion observations used at label endpoints are temporally valid;
- label provenance identifies raw quote, conversion source, time, rate, and policy;
- unavailable conversion produces explicit censoring/unavailability, not fabricated USD returns.

Evidence:

- `analysis/alpha/labels.py` defines the versioned conversion policy and local
  conversion observations, selects only unambiguous observations available at
  each endpoint, and records raw quote and conversion provenance on every label.
- Stablecoin parity is opt-in through the policy; other non-USD quotes without
  valid evidence are data-censored.
- `tests/test_phase3.py` covers future-observation exclusion, changing endpoint
  rates, explicit stablecoin treatment, conversion provenance, and unavailable
  conversion censoring.

## Slice 4R.5 — Token / pool / market identity closure

**Status:** DONE

Remove ambiguity between what was discovered (pool/market) and what is evaluated (token/asset).

Deliverables:

- explicit token, pool/market, venue, and constituent relationships or an equally rigorous canonical representation;
- normalized EVM pair/pool constituent decoding where supported;
- Tier-0 and Solana event normalization into the same conceptual identity contract;
- point-in-time relationship provenance;
- migration through the canonical storage boundary when persistent schema changes are required.

Acceptance:

- research never obtains token labels by accidentally reading a pool identity with the same-looking address field;
- symbol text is never an identity fallback;
- one pool with two constituents is represented unambiguously;
- EVM/Solana fixtures prove address-scoped identity and point-in-time relationship visibility.

Evidence:

- Schema version 6 adds a canonical, idempotent `asset_relationships` observation table linking a market to each address-scoped constituent, its structural role, venue, source, observation time, and raw evidence.
- Tier-0 persists provider-declared base/quote relationships; supported EVM factory logs decode the market plus both indexed constituents; Solana pool events retain a distinct pool identity and constituent links.
- Phase 3 resolves market discovery events through only relationships visible at the decision timestamp, evaluates constituent asset IDs rather than market IDs, and fails closed when the relationship was observed later.
- Fixture-only storage migration, Tier-0, EVM, Solana, and Phase 3 tests cover migration preservation, two-constituent representation, address-scoped identity, and point-in-time visibility.

## Slice 4R.6 — Short-horizon DEX/on-chain price observation contract

**Status:** DONE

Provide the persisted observations required by the declared 1h/6h/24h/7d label horizons for new-token research.

Deliverables:

- a provider-agnostic normalized price/liquidity observation contract for DEX/on-chain assets;
- configured cadence/resolution sufficient for supported label horizons;
- source identity and observation timestamps;
- missing/gap coverage semantics;
- replay-safe idempotent persistence;
- explicit capability/coverage reporting by chain/provider.

Acceptance:

- at least one EVM fixture path and one Solana fixture path can create a launch plus subsequent price observations through ingestion-owned adapters;
- Phase 3 builds labels solely from persisted observations with network disabled;
- gaps remain gaps; no synthetic interpolation is introduced;
- unsupported provider capabilities remain explicit.

Live-provider acceptance, when credentials are available, MUST be reported separately from fixture evidence.

Evidence:

- Schema version 7 adds source-scoped, idempotent DEX price/liquidity observations plus explicit
  per-chain/provider capability observations without filling absent intervals.
- GeckoTerminal's ingestion-owned adapter normalizes configured minute candles for address-scoped
  base assets and retains market, quote-asset, source, candle, and observation timestamps.
- The read-only dataset boundary consumes persisted DEX observations and carries quote identity into
  Phase 3 label conversion; an offline fixture proves persisted launch-to-1h-label replay.
- EVM and Solana Tier-0 fixtures cover subsequent observations, gap preservation, capability status,
  and replay-safe storage. Live provider behavior remains `UNVERIFIED_RUNTIME` without a credentialed
  or network-enabled smoke check.

## Slice 4R.7 — Phase 2 metric/time-index hardening

**Status:** ACTIVE

Make portfolio metrics safe for broader multi-asset and intraday research.

Deliverables:

- portfolio equity normalized to one canonical state per simulation timestamp before return calculation;
- annualization derived from declared observation frequency/time delta rather than a hard-coded daily assumption;
- documented behavior for irregular intervals;
- stale-signal policy across missing-bar gaps.

Acceptance:

- processing two assets at one timestamp cannot create two artificial portfolio return periods;
- 1h and 1d fixtures produce dimensionally correct annualization inputs;
- missing-gap execution behavior is explicit and tested;
- existing single-asset deterministic behavior remains compatible unless an approved correction requires a versioned semantic change.

## Slice 4R.8 — Canonical approved-research handoff

**Status:** PLANNED

Eliminate hand-assembled Phase 4 manifests as the normal integration path.

Deliverables:

- a versioned `ApprovedResearchResult` (name may vary) contract generated from a Phase 3 research run plus explicit human approval metadata;
- schema validation with unknown-field/required-field policy;
- content hashes for every staged/reportable research input;
- approval identity, reviewer, time, scope, and research-run identity;
- deterministic builder/validator for the handoff.

Acceptance:

- normal Phase 4 tests use the canonical builder rather than manually duplicating the schema;
- changing any approved research artifact invalidates the handoff;
- approval does not mutate the original research run;
- Phase 4 cannot consume an unapproved or unverifiable result.

## Slice 4R.9 — Evidence-bound claims and chart semantics

**Status:** PLANNED

Upgrade Phase 4 from evidence *reference* validation to evidence *derivation* validation where factual numbers are emitted.

Deliverables:

- typed numeric/comparative claim derivations (source field, operation, formatting/unit policy);
- validator proof that rendered claim values correspond to declared evidence/derivation;
- chart transformation whitelist tied to approved upstream semantics;
- annotations executed or rejected rather than silently ignored;
- stronger SVG/accessibility structural checks appropriate to the renderer.

Acceptance:

- a prose claim whose number disagrees with its referenced result fails validation;
- unsupported chart transformations fail closed;
- declared transformations are deterministic and represented in package provenance;
- missing/unsupported values cannot become zero or disappear without explicit representation.

## Slice 4R.10 — Phase 4 closure acceptance matrix

**Status:** PLANNED

Freeze the repaired Phase 1–4 contract before starting Phase 5.

Deliverables:

- Phase 3 acceptance matrix;
- Phase 4 acceptance matrix;
- one offline end-to-end fixture spanning persisted launch observation → point-in-time dataset → cohort/features/labels → governed candidate state → research artifact → explicit approval → report package;
- documentation reconciled with implemented behavior;
- unresolved provider/live checks listed separately.

Phase 4R is DONE only when:

- every mandatory matrix criterion is PASS or explicitly BLOCKED by an external prerequisite;
- no report claims a safeguard that execution does not implement;
- the end-to-end fixture requires no hand-authored semantic bridge between phases;
- all local gates and CI pass;
- `ROADMAP.md` is updated to make Phase 5 ACTIVE.

---

# Phase 5 — Research-Grade Data Reliability

**Status:** PLANNED  
**Depends on:** Phase 4R complete.  
**Goal:** Move from a correct local research chain to a measurable, recoverable observation system suitable for longitudinal studies.

## Slice 5.1 — Durable ingestion cursors

Persist per-source/per-chain progress so polling completeness is measurable and restarts do not depend solely on rolling lookbacks.

Acceptance includes restart replay, monotonic cursor rules, and explicit skipped-range detection.

## Slice 5.2 — EVM confirmation and reorg handling

Introduce confirmation depth, canonical block identity, and reorg reconciliation for event observations.

Acceptance includes simulated short reorgs and deterministic correction without silently deleting historical evidence.

## Slice 5.3 — Solana resumability and completeness

Replace bounded recent-window assumptions with a durable resumable discovery contract where provider capabilities allow it.

Acceptance includes high-activity fixtures proving no silent window loss.

## Slice 5.4 — Provider observation ledger and quality SLOs

Track expected/observed intervals, provider failures, rate-limit gaps, source latency, and completeness by source/chain.

Research eligibility must be able to consume these quality facts without live provider calls.

## Slice 5.5 — Two-store recovery protocol

Make DuckDB authoritative/cache semantics mechanically recoverable when Parquet publication diverges after a committed DB write.

Acceptance includes a simulated publication failure and automated deterministic repair/rebuild.

## Slice 5.6 — Historical conversion/reference series

Generalize the Phase 4R quote-currency policy into reusable point-in-time reference series with provenance and coverage metrics.

## Slice 5.7 — Data-plane closure matrix

Demonstrate restart, gap detection, reorg/recovery, multi-source selection, historical metadata/lineage, and price/conversion replay across representative chains.

---

# Phase 6 — Governed Experiment Control Plane

**Status:** PLANNED  
**Depends on:** Phase 5 data contracts stable.  
**Goal:** Make a complete research experiment a first-class, versioned, reproducible object rather than a composition of manually invoked helpers.

## Slice 6.1 — Experiment specification schema

Version cohort, feature, label, split, hypothesis family, correction policy, candidate definition, costs, baselines, and code/config identities in one declarative experiment spec.

## Slice 6.2 — Deterministic experiment runner

Execute the spec from local persisted inputs only and produce one immutable run directory/manifest.

## Slice 6.3 — Feature/label registry versioning

Give feature and label definitions durable identities, semantic versions, compatibility rules, and provenance hashes.

## Slice 6.4 — Hypothesis-family governance

Freeze multiplicity families before evaluation and prevent post-result silent redefinition.

## Slice 6.5 — Run catalog and comparison contract

Index immutable local research runs without mutating them; enable apples-to-apples comparisons only when methodology compatibility is proven.

## Slice 6.6 — Experiment CLI/API boundary

Expose a narrow local interface for validate → run → inspect → approve without creating a second execution engine.

## Slice 6.7 — Experiment-control acceptance matrix

Prove identical spec+data replay, rejected incompatible comparisons, sealed holdout behavior, and complete manifest reconstruction.

---

# Phase 7 — Robust Validation & Research Scaling

**Status:** PLANNED  
**Depends on:** Phase 6.  
**Goal:** Broaden statistical confidence without turning the repository into an automated optimizer that rewards overfitting.

## Slice 7.1 — Walk-forward / purged evaluation

Add explicitly configured walk-forward or purged evaluation for experiments that require repeated temporal validation.

## Slice 7.2 — Robust uncertainty

Add approved bootstrap/resampling methods where dependence structure permits them; retain method/config identity in artifacts.

## Slice 7.3 — Effect-size and minimum-evidence gates

Separate statistical significance from practical effect and require declared minimum evidence for promotion.

## Slice 7.4 — Cost/liquidity stress matrix

Evaluate candidate robustness across approved fee, slippage, liquidity, and missingness scenarios without changing the underlying candidate after holdout exposure.

## Slice 7.5 — Cohort/chain stability analysis

Measure whether results are dominated by one chain, era, liquidity band, provider, or small number of launches.

## Slice 7.6 — Negative controls and falsification suite

Introduce shuffled/permuted/known-null controls designed to reveal leakage and research-process false positives.

## Slice 7.7 — Validation closure matrix

Require replayable evidence that promoted results survive the configured robustness suite; passing remains a research result, not a profitability claim.

---

# Phase 8 — Research Product & Publication Operations

**Status:** PLANNED  
**Depends on:** Phase 7 for claims of validated research; descriptive packages may continue under Phase 4 rules.  
**Goal:** Turn approved evidence into maintainable research products without weakening provenance or human review.

## Slice 8.1 — Review/approval history

Represent approval, rejection, supersession, and reviewer notes as immutable records linked to exact research/package identities.

## Slice 8.2 — Rich deterministic output

Add HTML and/or PDF only if explicitly selected, with reproducible rendering/versioning and accessibility checks.

## Slice 8.3 — Artifact catalog/navigation

Provide local searchable metadata for research and report packages while preserving immutable underlying artifacts.

## Slice 8.4 — Optional model-assisted drafting boundary

If authorized, an LLM may draft from the validated claim ledger only. It may not create new facts, recompute research, or bypass claim validation. Deterministic evidence-bound output remains the source of truth.

## Slice 8.5 — Publication export boundary

Create exportable packages for human publication. External posting remains a separate explicit authorization and SHOULD NOT be coupled directly to research execution.

## Slice 8.6 — Publication closure matrix

Prove source-to-claim traceability, review history, renderer replay, accessibility, secret hygiene, and supersession behavior.

---

# Phase 9 — Optional Paper Execution

**Status:** DEFERRED

This phase is **not part of the current product commitment**. Start it only after an explicit product decision that the repository should become a trading/execution system.

If authorized, it requires a new design/threat model and a hard boundary between research outputs and paper orders. At minimum it would require broker/exchange adapters, account-state reconciliation, independent risk controls, kill switches, idempotent order intent, audit logs, and paper-only acceptance evidence.

Phase 8 completion does not imply Phase 9 should begin.

---

# Phase 10 — Optional Live Execution

**Status:** DEFERRED

Live-capital execution requires a separate explicit authorization after successful paper-execution validation, security review, operational monitoring, and failure-recovery testing. Nothing in Phases 1–8 authorizes live trading.

---

## 3. Cross-cutting technical debt policy

Do not create a parallel "cleanup phase." Address technical debt when one of these is true:

- it blocks the active slice;
- it invalidates an invariant or acceptance claim;
- it creates a material security/reproducibility risk;
- a small local correction is cheaper and safer than preserving the defect.

Otherwise record it as a scoped future slice rather than mixing it into unrelated work.

Known cross-cutting items to carry forward:

- explicit development/test dependency declaration in project metadata;
- documentation status reconciliation as phase behavior evolves;
- repository licensing decision before public distribution or outside contribution;
- branch/ruleset enforcement if/when repository/account capabilities permit it.

---

## 4. Roadmap maintenance contract

Every PR that completes a roadmap slice MUST update this file in the same PR:

- change the completed slice to **DONE**;
- record the landed commit/PR or concise evidence pointer when practical;
- make the next eligible slice **ACTIVE**;
- record new blockers discovered by executable evidence;
- do not rewrite historical completion claims without explaining why the prior claim became invalid.

When implementation reveals that ordering is wrong, change the ordering explicitly rather than bypassing it. Dependency correctness is more important than preserving phase numbers.

A roadmap-only edit MUST NOT mark implementation work DONE.

---

## 5. Agent handoff summary

For a fresh agent, the intended pickup sequence is:

`AGENTS.md` → `ROADMAP.md` → active `docs/plans/phase-*.md` → relevant code/tests → Git history/status.

The current frontier is **Phase 4R.7 — Phase 2 metric/time-index hardening**. Phase 4R.1 established the mandatory CI gate; do not begin Phase 5 until every mandatory Phase 4R closure criterion is satisfied.
