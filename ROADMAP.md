# Engineering Roadmap

**Status:** Active execution authority for forward work  
**Current phase:** Phase 6 governed experiment control plane
**Baseline:** `main` at `23dbd389af88cade4584cb5fdc10b60dc17fcc3b`
**Last reconciled:** 2026-09-15 (Slice 6.4 closed; Slice 6.5 active)

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

**Status:** DONE
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

- Schema version 13 adds source-scoped, idempotent DEX price/liquidity observations (`dex_price_observations`)
  plus explicit per-chain/provider capability observations (`observation_capabilities`) without filling
  absent intervals, alongside an idempotent generic `price_observations` table with address-scoped
  asset/market identity, observation time, positive price, quote asset, optional USD liquidity/volume,
  configured cadence, source, and raw evidence.
- `storage/db.py` provides deterministic upsert/read accessors for both observation contracts; migration
  and fresh/repeated initialization tests preserve existing rows and converge on the target contract.
- GeckoTerminal's ingestion-owned adapter normalizes configured minute candles for address-scoped
  base assets and retains market, quote-asset, source, candle, and observation timestamps; Tier-0 also
  normalizes GeckoTerminal base/quote USD prices, liquidity, volume, and the configured polling cadence
  into the generic observation contract.
- The read-only dataset boundary consumes persisted DEX observations and carries quote identity into
  Phase 3 label conversion; an offline fixture proves persisted launch-to-1h-label replay.
- EVM and Solana Tier-0 fixtures cover subsequent observations, gap preservation, capability status,
  address-scoped identities, and replay-safe storage for both observation contracts. Live provider
  behavior remains `UNVERIFIED_RUNTIME` without a credentialed or network-enabled smoke check.
- `tests/test_storage.py` and `tests/test_tier0.py` cover migration, idempotency, deterministic reads,
  address-scoped identities, optional values, and both network shapes.

## Slice 4R.7 — Phase 2 metric/time-index hardening

**Status:** DONE

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

Evidence:

- `analysis/backtesting/simulator.py` groups bars by timestamp and emits one
  portfolio state per timestamp. `BacktestConfig.stale_signal_policy` makes
  missing-gap handling explicit while preserving next-available execution as
  the default.
- `analysis/metrics/core.py` derives annualization periods from the declared
  observation frequency or timestamp intervals and reports interval spacing and
  irregularity.
- `tests/test_phase2.py` covers simultaneous multi-asset timestamps, 1h/1d
  annualization, irregular spacing, and stale-signal handling. The locked full
  suite passed with 84 tests and no network access.

## Slice 4R.8 — Canonical approved-research handoff

**Status:** DONE

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

Evidence:

- `reporting/package/handoff.py` provides the versioned `phase4-approved-v1`
  builder and strict validator. It stages only hash-verified Phase 3 artifacts,
  records approval identity/reviewer/time/scope and research-run identity, and
  produces a deterministic immutable handoff without modifying the source run.
- `reporting/package/generate.py` validates canonical handoffs before loading
  staged inputs. Phase 4 tests use the builder for normal fixtures and cover
  deterministic replay, changed-artifact rejection, unknown-field rejection,
  explicit approval, and unchanged Phase 3 source bytes.
- The locked full suite passed with 88 tests and no network access.

## Slice 4R.9 — Evidence-bound claims and chart semantics

**Status:** DONE

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

Evidence:

- `reporting/claims/model.py` now requires numeric factual claims to declare a
  source-field derivation, supported operation, unit, and decimal policy; it
  recomputes the value from staged evidence and rejects prose whose rendered
  number disagrees.
- `reporting/charts/spec.py` and `reporting/render/static.py` whitelist and
  execute `identity`/`sort_x` transformations and horizontal-line annotations;
  unsupported or unexecutable declarations fail closed. Chart semantics are
  retained in the package manifest, and the SVG validator checks parsed role,
  non-empty title/description, units, attribution, and non-finite output.
- `tests/test_phase4.py` covers derivation disagreement/missing declarations,
  transformation rejection, annotation execution/rejection, missing-value
  handling, deterministic replay, and the offline package path.
- The CI workflow pins the pytest/pluggy test-runner pair so the locked fixture
  verification does not depend on an ambient runner dependency.

## Slice 4R.10 — Phase 4 closure acceptance matrix

**Status:** DONE

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

Evidence:

- `docs/plans/phase-3-acceptance-matrix.md` and
  `docs/plans/phase-4-acceptance-matrix.md` freeze the mandatory local criteria,
  executable evidence, and separately blocked live/external checks.
- `tests/test_phase4.py::test_offline_phase1_to_phase4_chain_is_content_addressed_and_review_gated`
  denies network access and spans persisted launch observation, point-in-time
  dataset loading, cohort/feature/label construction, an explicit governed
  candidate decision, immutable research artifacts, the canonical approval
  handoff, and a deterministic pending-review report package.
- The locked full suite passed with 91 tests; byte compilation, the reporting
  guard, and whitespace validation also passed. Hosted CI remains the required
  merge-time confirmation.

---

# Phase 5 — Research-Grade Data Reliability

**Status:** ACTIVE
**Depends on:** Phase 4R complete.  
**Goal:** Move from a correct local research chain to a measurable, recoverable observation system suitable for longitudinal studies.

## Slice 5.1 — Durable ingestion cursors

**Status:** DONE

Persist per-source/per-chain progress so polling completeness is measurable and restarts do not depend solely on rolling lookbacks.

Acceptance includes restart replay, monotonic cursor rules, and explicit skipped-range detection.

Evidence:

- Schema version 8 adds the canonical `ingestion_cursors` table and a
  provider-agnostic storage API with source/scope identity, monotonic updates,
  compare-and-set continuity checks, run lineage, and deterministic reads.
- The EVM listener resumes each chain at the block after its durable `evm_rpc`
  cursor, advances only after a successful observation, permits idempotent
  overlap replay, and rejects a requested range that would silently skip
  blocks. The first observation retains the configured rolling lookback as an
  explicit bootstrap boundary.
- Fixture-only storage migration and listener restart tests cover v7-to-v8
  preservation, repeated initialization, per-chain isolation, regression and
  stale-writer rejection, restart continuation, and skipped-range failure.
  Solana's non-numeric signature continuation remains intentionally owned by
  Slice 5.3 rather than being coerced into this block-position contract.

## Slice 5.2 — EVM confirmation and reorg handling

**Status:** DONE

Introduce confirmation depth, canonical block identity, and reorg reconciliation for event observations.

Acceptance includes simulated short reorgs and deterministic correction without silently deleting historical evidence.

Evidence:

- Schema version 9 adds canonical EVM block observations keyed by chain, height,
  and block hash. Re-observed heights preserve orphaned hashes, enforce canonical
  parent continuity, and atomically mark linked EVM event observations orphaned.
- Configurable confirmation depth prevents the normal listener path from
  observing the unconfirmed head, while a configurable overlap window replays
  recent confirmed blocks on restart so short reorgs are detected.
- Fixture-only migration, listener, and storage tests cover v8-to-v9 event
  preservation, idempotent initialization, canonical block replacement, reorg
  audit events, and exclusion of orphaned observations from research snapshots.

## Slice 5.3 — Solana resumability and completeness

**Status:** DONE

Replace bounded recent-window assumptions with a durable resumable discovery contract where provider capabilities allow it.

Acceptance includes high-activity fixtures proving no silent window loss.

Evidence:

- Schema version 10 adds provider-agnostic opaque ingestion continuations with
  compare-and-set updates while preserving the numeric EVM cursor contract.
- The Helius enhanced-transaction client supports signature pagination. Each
  configured program resumes from its last durable signature, processes every
  intervening page oldest-to-newest, and advances only after persistence.
- Missing signatures, invalid paging limits, an unreachable prior signature,
  or exhaustion of the configured page budget fail closed without advancing
  progress. Initial observation remains an explicit one-page bootstrap boundary.
- Fixture-only migration and Solana listener tests cover v9-to-v10 row
  preservation, idempotent initialization, stale continuation writers,
  multi-page high-activity restart replay, and explicit gap failure. The locked
  full suite passed with 100 tests.

## Slice 5.4 — Provider observation ledger and quality SLOs

**Status:** DONE

Track expected/observed intervals, provider failures, rate-limit gaps, source latency, and completeness by source/chain.

Research eligibility must be able to consume these quality facts without live provider calls.

Evidence:

- Schema version 11 adds a `provider_observation_log` table keyed by
  `(source, scope, observed_at)` recording status (`success`, `failure`,
  `rate_limited`), latency, the configured expected poll interval, the
  observed gap since the prior attempt for that source/scope, rows observed,
  and error/run linkage.
- `storage/db.py` adds `record_provider_observation` (computes the observed
  gap from the last durable attempt), `classify_provider_failure` (rate-limit
  message heuristic consistent with the existing `safe_error_message`
  pattern), `read_provider_observation_log`, and `provider_quality_summary`
  (an offline, network-free aggregate of completeness ratio, average latency,
  worst observed gap, and last status per source/scope).
- `scheduler/pipeline.py` wires every scheduled job (`cex_refresh`,
  `tier0_poll`, `evm_listeners`, `solana_listener`, `normalization`) through
  `Pipeline.run_job`, which times each attempt, records success/failure/
  rate-limit outcomes at the job-name scope, and compares against
  `Pipeline.expected_job_intervals()` (derived from the same configured
  cadence used by `build_scheduler`).
- Per-source/chain granularity below the scheduled-job boundary: within one
  `evm_listeners` invocation, `Pipeline.evm_listeners()` now times and records
  each configured EVM chain individually under the `evm_rpc`/chain-name scope
  (the same identity already used for its durable ingestion cursor), and
  isolates each chain's failure so one unreachable RPC no longer prevents the
  remaining configured chains from being attempted that cycle. Within one
  `solana_listener` invocation, `ingestion/solana/listener.py::run_once` times
  and records each configured program under the `helius_enhanced`/address
  scope (the same identity already used for its durable signature
  continuation); a program failure is still recorded before propagating, so
  the whole run remains fail-closed per the Slice 5.3 contract rather than
  silently swallowing a gap.
- A documented research-eligibility gate: `analysis/alpha/eligibility.py`
  adds a pure `evaluate_chain_eligibility` function (plus `EligibilityPolicy`
  and `ChainEligibility`) that decides, per configured chain, whether its
  backing `(source, scope)` provider-quality rows clear configurable
  completeness/gap/last-status thresholds -- explicitly distinguishing a
  chain with no configured scope or no recorded observations from one that is
  merely unhealthy. It is a pure function over already-fetched
  `provider_quality_summary` rows, preserving the existing `analysis/alpha`
  boundary of never reading `storage/db.py` directly. `CohortConfig` gains an
  optional `chain_eligibility` field; `extract_cohort` in
  `analysis/alpha/cohort.py` treats a chain that fails this gate as a new,
  explicit `CHAIN_PROVIDER_QUALITY_INELIGIBLE` exclusion reason -- retained in
  the cohort with full evidence per the Phase 3 inclusion/exclusion
  invariant, distinct from and decided before the existing liquidity/coverage
  analysis-eligibility tier documented in
  `docs/plans/phase-3-authoritative-decisions.md`.
- `tests/test_storage.py` covers the v10-to-v11 migration preserving existing
  cursor rows, fresh/repeated initialization, gap computation, the offline
  quality summary aggregate, unsupported-status rejection, and the rate-limit
  classifier. `tests/test_scheduler.py` covers a full cycle populating the
  ledger with the configured expected intervals, a rate-limited failure being
  classified and persisted distinctly from a generic failure, a per-chain EVM
  observation being recorded, and one EVM chain's failure being isolated from
  a second chain's success within the same job invocation.
  `tests/test_solana.py` covers a per-program observation being recorded on
  success and a program failure being recorded before the run still raises.
  `tests/test_eligibility.py` covers healthy/unhealthy/unobserved/
  multi-scope chains and policy validation. `tests/test_phase3.py` covers a
  cohort excluding an ineligible chain while an unaffected chain's exclusion
  reason is decided independently, a chain with no provider evidence being
  treated as ineligible rather than defaulting to healthy, and unchanged
  behavior when no `chain_eligibility` is supplied. The locked full suite
  passed with 121 tests; the storage migration guard reported the fresh and
  migrated schemas as converged.

## Slice 5.5 — Two-store recovery protocol

**Status:** DONE

Make DuckDB authoritative/cache semantics mechanically recoverable when Parquet publication diverges after a committed DB write.

Acceptance includes a simulated publication failure and automated deterministic repair/rebuild.

Evidence:

- `storage/db.py` adds `list_ohlcv_partitions` (every `(source, date)` partition
  the authoritative `ohlcv` table currently holds), `verify_parquet_publication`
  (compares each partition's DuckDB content against its published Parquet
  file and classifies it `missing`, `unreadable`, or `stale` without changing
  anything), and `repair_parquet_publication` (rebuilds only the diverging
  partitions from DuckDB using the same stage-to-temp-file-then-atomic-`os.replace`
  sequence normal ingestion uses, so a crash mid-repair still leaves every
  partition at either its prior or its fully repaired state). `insert_ohlcv_batch`
  is unchanged in its committed-then-publish ordering; its exception path now
  documents that a raised publication failure leaves DuckDB authoritative and
  recoverable through this repair path rather than a lost write.
- No `SCHEMA_VERSION` change was required: Parquet is fully derivable from the
  authoritative DuckDB `ohlcv` rows, so recovery needed no new persisted
  divergence-tracking state, consistent with the storage-schema-migration
  skill's scope (persisted-contract changes only).
- `python -m storage <db> --verify-parquet` and `--repair-parquet` expose the
  same functions as an operator-facing CLI (`storage/__main__.py`), replacing
  the prior manual "rerun the same ingestion write" guidance in
  `docs/RUNBOOK.md`, which now documents the mechanical recovery commands.
- `tests/test_storage.py` covers detecting missing, unreadable, and stale
  partitions in one store; deterministic repair of all three; idempotent
  repair against an already-repaired store; and a simulated `os.replace`
  publication failure during `insert_ohlcv_batch` proving the DuckDB write
  stays committed and is fully recoverable via `--repair-parquet` without
  re-ingesting. The locked full suite passed with 123 tests; byte-compilation
  and whitespace validation also passed.

## Slice 5.6 — Historical conversion/reference series

**Status:** DONE

Generalize the Phase 4R quote-currency policy into reusable point-in-time reference series with provenance and coverage metrics.

Evidence:

- Schema version 12 adds a canonical `reference_series` table keyed by
  `(series_id, observed_at, source)` holding a positive value plus
  evidence, generalizing the Phase 4R quote-conversion overlay into a
  persisted, provider-agnostic point-in-time series contract that is not
  limited to label-boundary USD conversion.
- `storage/db.py` adds `upsert_reference_series_observation` (idempotent
  upsert), `read_reference_series` (deterministic ordered read), and
  `reference_series_coverage_summary` (an offline, network-free aggregate
  of per-series observation count, distinct-source count, first/last
  observed time, last source, and worst observed gap), mirroring the
  Slice 5.4 provider-quality-summary pattern for coverage/provenance
  evidence.
- `analysis/datasets/snapshot.py` exposes the persisted series through
  `DatasetSnapshot`: a `reference_series` field (deduplicated and ordered
  by `series_id`/`observed_at`/`source`, rejecting duplicate identity) and
  a `reference_series_at(series_id, decision_time)` point-in-time accessor
  consistent with the existing `metadata_at`/`relationships_at` boundary.
  `from_duckdb` loads it as a required table and folds it into the
  dataset's content-addressed identity hash.
- `analysis/alpha/labels.py` sources quote/USD conversion evidence from
  `snapshot.reference_series_at(f"{quote}/USD", point)` in addition to any
  explicitly supplied `ConversionObservation` tuple, so a persisted
  reference series can back label conversion without every caller having
  to hand-assemble observations; explicit observations, stablecoin parity,
  fail-closed unavailability, and existing provenance fields are
  unchanged.
- `tests/test_storage.py` covers the v11-to-v12 migration preserving the
  provider observation log, idempotent upsert, deterministic read, and the
  offline coverage summary (count, source count, first/last observed time,
  last source, max gap). `tests/test_phase3.py` covers
  `DatasetSnapshot.reference_series_at` point-in-time visibility and
  duplicate-identity rejection, and a label generated purely from a
  persisted reference series (no explicit `conversion_observations`)
  proving temporally valid selection and unchanged provenance shape. The
  locked full suite passed with 127 tests; the storage migration guard
  reported the fresh and migrated schemas as converged; byte-compilation
  and whitespace validation also passed.

## Slice 5.7 — Data-plane closure matrix

**Status:** DONE

Demonstrate restart, gap detection, reorg/recovery, multi-source selection, historical metadata/lineage, and price/conversion replay across representative chains.

Evidence:

- `docs/plans/phase-5-data-plane-closure-matrix.md` freezes the executable
  Phase 5 data-plane contract: durable EVM cursor restart, EVM/Solana gap
  detection failing closed, EVM reorg reconciliation, Solana resumable
  multi-page discovery, the provider observation ledger and offline quality
  summary, the research-eligibility gate, DuckDB/Parquet recovery, and
  reference-series-backed conversion replay, each with executable evidence
  and status.
- `tests/test_phase5_closure.py` adds no new production behavior. It proves
  the Slice 5.1-5.6 guarantees compose in one local, offline dataset across
  two representative chains: durable-cursor EVM restart composes with reorg
  reconciliation and rejects a subsequent skipped range
  (`test_evm_cursor_restart_and_reorg_compose_and_gap_detection_fails_closed`);
  Solana's durable-signature discovery fails closed on an unreachable
  checkpoint without advancing progress
  (`test_solana_gap_detection_fails_closed_without_advancing_progress`); and
  the full composed flow denies socket creation while threading Solana's
  resumable multi-page discovery, a research-eligibility gate computed from
  real persisted provider-quality rows (two healthy representative chains
  plus one never-observed chain failing closed), a detected-and-repaired
  Parquet publication gap, and ETH/USD- and SOL/USD-backed forward-return
  labels sourced purely from persisted reference series, through the real
  Phase 1 storage boundary into Phase 3 cohort extraction and label
  generation for both chains
  (`test_phase5_data_plane_closure_across_representative_evm_and_solana_chains`).
  That same test also proves a malformed/unresolved event identity (the
  Solana listener's own real transaction shape, which carries no
  address-identifying key the cohort rule recognizes) is retained as an
  explicit exclusion rather than silently collapsed onto the resolved token.
- The closure matrix doc records one deliberate scope boundary: EVM
  `chain_reorg_detected` audit events are canonical-id-scoped to a synthetic
  block identity, not a persisted asset, so composing them into the same
  store `DatasetSnapshot.from_duckdb` loads would trip its existing
  unknown-asset-identity validation -- a Phase 1/3 integrity guarantee this
  slice preserves rather than weakens. EVM restart/reorg/gap-detection is
  therefore proven in an isolated store, and only the resulting
  provider-quality outcome (exactly what `Pipeline.evm_listeners` itself
  records) feeds the composed research dataset. No mandatory Slice 5.1-5.6
  acceptance criterion required otherwise, and no existing behavior changed.
- The locked full suite passed with 130 tests (127 prior + 3 new); the
  storage migration guard, byte-compilation, and whitespace validation also
  passed.

Phase 5 is **DONE**: every Slice 5.1-5.7 acceptance criterion is satisfied by
executable, offline fixture evidence, and the composed closure matrix proves
those guarantees hold together rather than only in isolation. Live-provider
acceptance and production-scale longitudinal sample adequacy remain
explicitly out of scope and separately blocked, per the closure matrix doc.

---

# Phase 6 — Governed Experiment Control Plane

**Status:** ACTIVE
**Depends on:** Phase 5 data contracts stable (DONE -- see Phase 5 above).
**Goal:** Make a complete research experiment a first-class, versioned, reproducible object rather than a composition of manually invoked helpers.

## Slice 6.1 — Experiment specification schema

**Status:** DONE

Version cohort, feature, label, split, hypothesis family, correction policy, candidate definition, costs, baselines, and code/config identities in one declarative experiment spec.

Evidence:

- `analysis/experiments/spec.py` adds the versioned, frozen `ExperimentSpec`
  (`phase6-experiment-v1`) composing the existing governed Phase 3 objects
  (`CohortConfig`, `LabelDefinition`, `PromotionPolicy`) with new versioned
  declarative components: `SplitPolicy` (chronological split window
  configuration), `HypothesisFamily` (the frozen feature/threshold/horizon/
  subgroup grid plus its discovery/confirmation correction identity),
  `CandidateDefinition` (a selection-rule identity string rather than an
  executable callable), `CostPolicy` (turnover/cost scenarios), and
  `BaselinePolicy` (required baseline families). `code_version` and
  `config_identity` are required scalar identities on the spec itself.
- The spec never executes cohort extraction, feature computation, labeling,
  splitting, or candidate evaluation; it only versions, cross-validates, and
  content-identifies configuration those already-governed Phase 3 helpers
  consume, preserving the "compose, don't duplicate" boundary for Phase 6.
- Cross-component validation fails closed rather than silently drifting:
  hypothesis-family/candidate horizons must be declared by the spec's own
  labels, the split's label-horizon window must cover the longest declared
  label horizon, and the promotion policy's correction method/thresholds
  must match the hypothesis family's declared correction identity. Only the
  currently implemented `benjamini-hochberg`/`holm-bonferroni` corrections
  and the existing `baseline_families` names are accepted.
- `experiment_spec_id` produces a deterministic sha256-derived content
  identity (mirroring the existing run/handoff id pattern in
  `analysis/alpha/artifacts.py` and `reporting/package/handoff.py`); the same
  spec fields always hash identically, and changing any versioned component
  (split embargo, hypothesis threshold, cost scenario, etc.) changes the
  identity.
- `tests/test_phase6.py` covers deterministic identity replay, an identity
  change from each versioned component, feature-set normalization/dedup,
  and fail-closed rejection of unsupported spec/correction versions,
  undeclared horizons, a split window shorter than the longest label
  horizon, a promotion-policy/hypothesis-family correction mismatch, and
  invalid baseline/cost/candidate/split configuration. The locked full suite
  passed with 154 tests (130 prior + 24 new); the storage migration guard,
  byte-compilation, and whitespace validation also passed.

## Slice 6.2 — Deterministic experiment runner

**Status:** DONE

Execute the spec from local persisted inputs only and produce one immutable run directory/manifest.

Evidence:

- `analysis/experiments/runner.py` adds `run_experiment(spec, snapshot, output_dir)`,
  the first code that actually executes an `ExperimentSpec`. It composes only the
  already-governed Phase 3 helpers (`extract_cohort`, `compute_features`,
  `generate_labels`, `build_split`, `score_candidate`, `baseline_families`,
  `evaluate_candidate_promotion`) in the sequence the spec declares, and never
  redefines cohort, feature, label, split, or candidate-evaluation semantics.
- `resolve_feature_registry` maps only the spec's declared feature identities that
  have an implemented, versioned definition (`launch_liquidity_usd`,
  `lookback_return`) to the canonical `analysis/alpha/features.py` constructors,
  failing closed on any other declared identity rather than substituting a
  different computation. A declarative `feature>=pXX` candidate selection rule is
  resolved to concrete token ids using only feature values observed inside the
  partition being scored (the discovery split), so no other-partition information
  can leak into the selection boundary; an unsupported rule fails closed.
- The runner deliberately does not fabricate hypothesis-family significance
  testing: `discovery_adjusted_p_value`/`holdout_adjusted_p_value` are left unset
  because frozen multiplicity-family execution is Slice 6.4's job, so
  `evaluate_candidate_promotion` honestly returns `insufficient_evidence` with an
  explicit `MISSING_DISCOVERY_CORRECTION` reason rather than an invented pass.
  `baseline_superior`, `uncertainty_supports_effect`, and `cost_sensitivity_passed`
  are derived directly and deterministically from the already-computed
  `CandidateResult` fields.
- The run identity is keyed by the spec's own content-addressed
  `experiment_spec_id` plus the dataset identity and code version (mirroring the
  existing `analysis/alpha/artifacts.py::write_research_run` and
  `analysis/runs/artifacts.py::write_run` immutable-write pattern); an identical
  spec/dataset/code-version replay is byte-identical, and changing any of them
  produces a distinct run directory. Secret-bearing fields are sanitized before
  being written, following the same pattern already used by the other two
  artifact writers.
- `tests/test_phase6.py` adds a full-coverage eight-launch fixture and covers:
  end-to-end execution through every declared step producing all eight expected
  artifacts; byte-identical replay; run-identity change on a spec change; a
  rejected unresolved feature identity; a rejected unsupported selection rule;
  and a selection threshold computed strictly within the discovery partition
  (never a validation/holdout launch). The locked full suite passed with 179
  tests (154 prior + 25 new); the storage migration guard, byte-compilation, and
  whitespace validation also passed.

## Slice 6.3 — Feature/label registry versioning

**Status:** DONE

Give feature and label definitions durable identities, semantic versions, compatibility rules, and provenance hashes.

Evidence:

- `analysis/alpha/features.py` adds a required `version` field to
  `FeatureDefinition` (fails closed on a blank version) and
  `feature_definition_id`, a deterministic sha256 content hash over every
  declared, hashable field (name, version, source columns, effective
  timestamp, lookback, missing-value policy, allowed horizons, source
  timestamp). The `compute` callable itself is intentionally excluded from
  the hash: its behavior per (name, version) is governed by catalog
  discipline rather than hashed Python code, the same pattern already used
  for other Phase 3 config objects.
- `analysis/alpha/labels.py` adds `LABEL_SEMANTIC_VERSIONS` (the currently
  implemented semantic version of each horizon's tolerance/censoring
  contract) and a required `version` field on `LabelDefinition` that must
  match its horizon's implemented version, failing closed on an
  unimplemented one. `label_definition_id` content-hashes a label's declared
  semantic fields (name, version, horizon, quote currency, censoring
  policy, unavailable treatment).
- Every produced feature value and label row now carries its own resolved
  `feature_version`/`feature_definition_id` or `label_version`/
  `label_definition_id` in its provenance, so a value can be traced to the
  exact versioned definition that produced it, not just a bare name.
- `analysis/alpha/registry.py` adds the durable catalog layer: `FEATURE_POLICIES`
  (named bundles of per-feature versions, e.g. `phase3-feature-v1`),
  `resolve_feature_definition`/`feature_policy_versions` (fail closed on an
  unknown policy or (name, version) pair), and `FEATURE_COMPATIBILITY`/
  `LABEL_COMPATIBILITY` with `assert_feature_versions_compatible`/
  `assert_label_versions_compatible` — compatibility fails closed by default
  and only an explicit declared entry permits treating two versions of the
  same name as comparable. Only `v1` of each feature/label exists today, so
  no compatibility entry is populated yet; the assertions are exercised
  directly by tests ahead of Slice 6.5's run-comparison consumer.
- `analysis/experiments/spec.py` resolves `ExperimentSpec.feature_policy_version`
  against the registry catalog at spec construction time, so an unresolved
  feature identity now fails closed earlier (spec construction) rather than
  only at runner resolution; `analysis/experiments/runner.py` resolves
  features through the same catalog and writes a new `definitions.json` run
  artifact recording the resolved version and content-addressed identity of
  every feature and label the run actually used.
- `tests/test_phase6.py` covers: feature/label version validation
  (blank/unimplemented versions fail closed), deterministic content-hash
  replay and change-on-version/change-on-censoring-policy, hash independence
  from the `compute` callable, policy/catalog resolution success and
  fail-closed cases, compatibility-assertion identity/undeclared-pair
  behavior, per-row feature/label provenance carrying the resolved
  identity, the earlier (spec-construction-time) unresolved-feature
  rejection, and the new `definitions.json` run artifact. The locked full
  suite passed with 193 tests (179 prior + 14 new); the storage migration
  guard, byte-compilation, and whitespace validation also passed.

## Slice 6.4 — Hypothesis-family governance

**Status:** DONE

Freeze multiplicity families before evaluation and prevent post-result silent redefinition.

Evidence:

- `analysis/experiments/hypotheses.py` expands every declared
  feature/threshold/horizon/subgroup cell into a deterministic frozen family
  manifest whose content identity is bound to the complete grid, correction
  policies, thresholds, and experiment-spec identity.
- Family evaluation verifies that the frozen content still matches its identity
  and requires an exact key match between the predeclared grid and submitted raw
  p-values. Missing or extra cells fail closed, while explicit unavailable
  (`None`) results remain present and rejected rather than disappearing from the
  correction denominator.
- Discovery applies the declared Benjamini-Hochberg policy and confirmation
  applies the declared Holm-Bonferroni policy, with every corrected result bound
  to the frozen `family_id`. The experiment runner freezes this manifest before
  inspecting cohort or result data and persists it as
  `hypothesis_family.json`; it still does not invent unavailable raw p-values.
- `ExperimentSpec` now also rejects hypothesis features outside its declared
  feature set. `tests/test_phase6.py` covers deterministic grid expansion,
  identity changes, narrowed/widened submissions, modified frozen content,
  correction binding, explicit unavailable results, spec cross-validation, and
  the runner artifact. The locked full suite passed with 362 tests; the storage
  migration guard, byte-compilation, and whitespace validation also passed.

## Slice 6.5 — Run catalog and comparison contract

**Status:** ACTIVE

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

The current frontier is **Slice 6.5 — Run catalog and comparison contract**.

Phase 5 is DONE. Slice 5.7 closed the phase with
`docs/plans/phase-5-data-plane-closure-matrix.md` and
`tests/test_phase5_closure.py`, proving the composed data-plane guarantees
Phase 5 built hold together across two representative chains rather than
only in isolation: durable-cursor restart replay (5.1), EVM reorg
detection/recovery (5.2), Solana resumable/complete discovery (5.3), provider
quality/eligibility gating (5.4), DuckDB/Parquet recovery (5.5), and
historical/reference-series-backed conversion replay (5.6), plus explicit
gap-detection fail-closed paths for both EVM and Solana (see the Slice 5.7
evidence above). Live-provider acceptance (credentialed EVM RPC and Helius)
and production-scale longitudinal sample adequacy remain explicitly
out of scope and separately blocked, per the closure matrix doc.

Slice 6.1 is DONE. `analysis/experiments/spec.py` defines the versioned,
declarative `ExperimentSpec` (`phase6-experiment-v1`) covering cohort,
feature, label, split, hypothesis family, correction policy, candidate
definition, costs, baselines, and code/config identities in one
cross-validated, content-addressed object, composing the existing governed
`analysis/alpha/` types (`CohortConfig`, `LabelDefinition`,
`PromotionPolicy`) rather than duplicating them.

Slice 6.2 is DONE. `analysis/experiments/runner.py::run_experiment` takes an
`ExperimentSpec` plus a local `DatasetSnapshot` and executes the
already-governed Phase 3 helpers (`extract_cohort`, `compute_features`,
`generate_labels`, `build_split`, `score_candidate`, `baseline_families`,
`evaluate_candidate_promotion`) in the sequence the spec declares, producing
one immutable run directory/manifest keyed by `experiment_spec_id` plus
dataset identity and code version, with no recomputation or redefinition of
Phase 3 research semantics. It deliberately leaves hypothesis-family
significance evidence (`discovery_adjusted_p_value`/
`holdout_adjusted_p_value`) unset rather than fabricating it, so promotion
honestly reports `insufficient_evidence` until real multiplicity-family
testing lands.

Slice 6.3 is DONE. `analysis/alpha/features.py` and `analysis/alpha/labels.py`
now require a `version` on every `FeatureDefinition`/`LabelDefinition` (a
label's version must match its horizon's implemented semantic version) and
expose `feature_definition_id`/`label_definition_id`, deterministic
content hashes of each definition's declared semantic fields, recorded on
every produced feature/label row's own provenance. `analysis/alpha/registry.py`
adds the durable catalog (`FEATURE_POLICIES`, `resolve_feature_definition`,
`feature_policy_versions`) that replaced the ad hoc bare-name-to-constructor
mapping `resolve_feature_registry` used in Slice 6.2, plus
`assert_feature_versions_compatible`/`assert_label_versions_compatible`,
which fail closed on any undeclared cross-version comparison so Slice 6.5's
run-comparison contract has a compatibility rule to enforce rather than
having to invent one. `ExperimentSpec` now resolves `feature_policy_version`
against this catalog at construction time, and every experiment run writes
a `definitions.json` artifact recording the resolved version and
content-addressed identity of every feature/label the run actually used.

Slice 6.4 is DONE. `analysis/experiments/hypotheses.py` expands the complete
declared grid into a content-addressed `FrozenHypothesisFamily`, verifies its
identity at evaluation, and accepts raw results only when their keys exactly
match that frozen grid. Discovery and confirmation corrections are therefore
bound to the same immutable family rather than a post-result narrowed or
widened set. `run_experiment` creates and persists the family commitment before
inspecting research results while continuing to leave unavailable significance
evidence explicit rather than fabricating it.

Slice 6.5 has not started. It needs to index immutable local experiment runs
without mutating them and permit comparisons only after the feature/label and
methodology compatibility contracts prove they are apples-to-apples.
