# Engineering Roadmap

**Status:** Active execution authority for forward work  
**Current phase:** Phase 8R empirical research readiness
**Baseline:** `main` at `1656dd9` (Slice 8R.7b focused evidence: 141 passed)
**Last reconciled:** 2026-09-16 (Slice 8R.7b integrates validated significance evidence into
immutable experiment runs; Slice 8R.7c is ACTIVE and 8R.7 remains subject to the unavailable
independent methodological reviewer; Phase 8R remains open; Phases 9–10 remain deferred)

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

- **Phase 1 ingestion/storage:** CEX, Tier-0 DEX, EVM, Solana, normalization, scheduling, DuckDB/Parquet persistence, schema version 13, timestamped metadata/lineage observations, source-scoped OHLCV, and short-horizon DEX/on-chain observations.
- **Phase 2 backtesting:** read-only point-in-time snapshots, a narrow strategy protocol, deterministic single-CEX next-bar-open simulation, fees/slippage, metrics, and immutable run artifacts.
- **Phase 3 research:** cohort extraction, temporal feature registry, fixed-horizon labels, purged chronological discovery/validation/holdout partitions, governed candidate-promotion states, multiple-testing helpers, deterministic research artifacts, and Phase-2-compatible handoff metadata.
- **Phase 4 reporting:** hash-verified Phase 3 linkage, hash-verified staged inputs, claim/chart and derivation validation, deterministic SVG/HTML rendering, Markdown package generation, secret checks, immutable package artifacts, human review attestations/history, catalog navigation, and human-gated publication export.
- **Phase 6–7 experiment control and validation:** deterministic experiment identity, frozen hypothesis families, chronological discovery/validation/holdout separation with purge/embargo semantics, candidate promotion gates, uncertainty/effect-size evidence, stress testing, stability analysis, negative controls, optional walk-forward evaluation, and validation-closure evidence.
- **Phase 8 research product operations:** immutable experiment/report artifacts, deterministic reporting, immutable review history, artifact catalog/navigation, and local publication export. Phase 8 is complete; these capabilities do not by themselves establish empirical research validity or authorize execution.
- **Cross-phase evidence:** the test suite includes an offline, content-addressed Phase 1 → Phase 3 → approved Phase 4 fixture chain.
- **Continuous verification:** GitHub Actions runs the locked fixture/unit suite, storage migration guard, byte-compilation, and whitespace checks for pull requests and `main` without provider credentials.

The latest hardening work fixed several earlier weaknesses: metadata/lineage history is retained by observation time, OHLCV is source-scoped, ambiguous source selection fails closed, Phase 3 run identity commits to artifact hashes, and Phase 4 verifies linked research/staged content hashes.

### 2.1 What is *not* yet proven complete

The repository has largely built the laboratory. The active frontier is proving
that it can produce credible empirical conclusions from realistic historical
crypto data. In particular, the following remain open for Phase 8R:

- deterministic dataset-quality and coverage evidence bound to exact dataset profiles;
- a fixed scientific benchmark corpus for leakage, null, bias, identity, conversion, missingness, and robustness behavior;
- durable research-question and hypothesis identities that preserve the question → hypothesis → experiment specification → result distinction;
- a declared, evidence-bound falsification policy rather than post-hoc robustness selection;
- a reproducible research-campaign provenance object spanning rejected and promoted hypotheses, evidence, limitations, and conclusion;
- at least one complete real-data research campaign with honest positive or negative outcome handling;
- an independent methodological audit before any execution phase can become active.

Earlier data-plane limitations remain research inputs and must be characterized
by the dataset-profile evidence rather than hidden behind a generic quality
score. Dataset correctness, completeness, representativeness, and fitness for a
particular research question are distinct claims.

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

**Status:** DONE
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

**Status:** DONE
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

**Status:** DONE

Index immutable local research runs without mutating them; enable apples-to-apples comparisons only when methodology compatibility is proven.

Evidence:

- `analysis/experiments/catalog.py` adds a read-only catalog loader that verifies
  the manifest version and immutable marker, run identity, required artifact
  presence, and every declared artifact hash before exposing run metadata.
  Deterministic directory indexing reads immediate immutable runs without
  creating or modifying catalog state.
- The comparison boundary first verifies both runs, then requires identical
  feature and label sets, applies the registry's explicit cross-version
  compatibility rules, and requires all remaining methodology fields to match.
  It exposes only deterministic candidate summary deltas after those gates pass;
  incompatible cost or other methodology changes fail closed.
- `tests/test_phase6.py` covers deterministic non-mutating indexing, artifact and
  identity tamper rejection, compatible comparison, and fail-closed methodology
  mismatch. The locked full suite passed with 366 tests; the storage migration
  guard, byte-compilation, and whitespace validation also passed.

## Slice 6.6 — Experiment CLI/API boundary

**Status:** DONE

Expose a narrow local interface for validate → run → inspect → approve without creating a second execution engine.

Evidence:

- `analysis/experiments/control.py` exposes spec loading/validation, execution,
  verified inspection, and explicit human approval functions by delegating to
  the existing `ExperimentSpec`, runner, and catalog boundaries. Canonical JSON
  specs reconstruct the same nested validated dataclasses used by Python callers;
  unknown or malformed schema fields fail closed.
- `python -m analysis.experiments` provides matching `validate`, `run`,
  `inspect`, and `approve` commands. The run command materializes one read-only
  local `DatasetSnapshot` and invokes the sole experiment runner; it contains no
  alternate cohort, feature, label, split, selection, or evaluation logic.
- Approval first hash-verifies the immutable run and writes a content-addressed,
  reviewer-attributed, timestamped attestation outside the run directory. It
  does not mutate promotion evidence, unseal holdout data, authorize trading, or
  imply publication. `tests/test_phase6.py` covers spec round-trip/rejection,
  API delegation, CLI validation/inspection/approval, immutable approval replay,
  run non-mutation, required attribution, and tampered-run rejection.

## Slice 6.7 — Experiment-control acceptance matrix

**Status:** DONE

Prove identical spec+data replay, rejected incompatible comparisons, sealed holdout behavior, and complete manifest reconstruction.

Evidence:

- `docs/plans/phase-6-experiment-control-closure-matrix.md` maps every Phase 6
  control-plane criterion to executable offline evidence and preserves the
  boundary between deterministic fixture acceptance and claims of alpha,
  profitability, live-provider readiness, or production-scale adequacy.
- `tests/test_phase6_closure.py` composes the public spec loader, sole runner,
  immutable manifest, verified inspector, and comparison boundary. It proves
  identical spec+data reconstruction resolves to the same byte-verified run,
  every run artifact is declared and hash-valid, and the path remains offline.
- The closure fixture changes only sealed-holdout price evidence and observes
  changed label output while discovery-derived candidate and promotion output
  remains byte-identical. A changed cost methodology is rejected by the
  comparison boundary rather than presented as an apples-to-apples result.

---

# Phase 7 — Robust Validation & Research Scaling

**Status:** DONE
**Depends on:** Phase 6.  
**Goal:** Broaden statistical confidence without turning the repository into an automated optimizer that rewards overfitting.

## Slice 7.1 — Walk-forward / purged evaluation

**Status:** DONE

Add explicitly configured walk-forward or purged evaluation for experiments that require repeated temporal validation.

Evidence:

- `SplitPolicy` now declares either the existing `single_split` behavior or a
  content-addressed `walk_forward` mode with an explicit fold count; invalid
  modes, fewer than two folds, and undersized cohorts fail closed.
- `analysis/experiments/walk_forward.py` deterministically reserves the final
  20 percent as sealed holdout evidence and constructs expanding training plus
  non-overlapping validation folds. Each boundary applies the declared label
  purge, feature-lookback purge, and embargo rules while retaining row-level
  removal reasons.
- The sole experiment runner learns each selection threshold from that fold's
  training rows, evaluates only its validation rows, and emits the fold
  membership, thresholds, baselines, candidate summaries, temporal policy, and
  sealed holdout in hash-bound `walk_forward.json`. It never scores holdout rows
  through this path.
- `tests/test_phase7.py` covers expanding/non-overlapping membership, holdout
  isolation, purge/embargo evidence, deterministic input-order replay,
  insufficient data, configuration validation, and runner/manifest integration.
  The locked full suite passed with 378 tests; the version-1 storage migration
  guard, byte-compilation, and whitespace validation also passed.

## Slice 7.2 — Robust uncertainty

**Status:** DONE

Add approved bootstrap/resampling methods where dependence structure permits them; retain method/config identity in artifacts.

Evidence:

- `analysis/experiments/uncertainty.py` adds the versioned, fail-closed
  `moving_block_bootstrap` estimator for ordered dependent observations with
  deterministic resampling and percentile intervals. Empty or undersized
  evidence remains explicitly unavailable.
- `UncertaintyPolicy` is part of the content-addressed experiment spec, and
  every run emits hash-bound `uncertainty.json` containing the complete method
  and configuration identity. `tests/test_phase7.py` covers deterministic
  replay, unsupported dependence, explicit missingness, and manifest linkage.
- The locked full suite, byte compilation, and whitespace checks passed for
  this slice. The storage migration guard was not applicable because storage
  schema/accessor files were unchanged. Live-provider behavior remains
  outside the slice and unverified.

## Slice 7.3 — Effect-size and minimum-evidence gates

**Status:** DONE

Separate statistical significance from practical effect and require declared minimum evidence for promotion.

Evidence:

- `PromotionPolicy.minimum_effect_size` declares the practical-effect floor;
  `PromotionEvidence.effect_size` records the measured candidate-minus-baseline
  effect separately from uncertainty/significance evidence.
- Missing effect evidence remains `insufficient_evidence`, while a finite effect
  below the declared floor is rejected with `PRACTICAL_EFFECT_TOO_SMALL`.
  Existing sample-size, independent-launch, and coverage gates remain mandatory.
- `tests/test_phase3.py` covers missing and below-floor effect evidence, and the
  runner/README preserve the contract in deterministic experiment outputs.
- Focused and repository-wide fixture verification for this slice passed; live
  provider behavior remains outside scope and unverified.

## Slice 7.4 — Cost/liquidity stress matrix

**Status:** DONE

Evaluate candidate robustness across approved fee, slippage, liquidity, and missingness scenarios without changing the underlying candidate after holdout exposure.

Evidence:

- `StressPolicy` adds a versioned, declarative set of approved fee-rate,
  slippage, minimum-liquidity, and explicit missingness dimensions to the
  content-addressed experiment spec. Unsupported, negative, duplicate, or
  empty dimensions fail closed.
- `analysis/experiments/stress.py` evaluates the Cartesian stress matrix
  against the discovery-selected token ids only. It reprices the fixed
  candidate for fee/slippage, applies liquidity exclusions from the resolved
  feature rows, and reports incomplete evidence as explicit unavailable
  scenarios rather than imputing it. No validation or sealed-holdout row can
  influence selection or stress membership.
- The runner persists hash-bound `stress_matrix.json` in every run, including
  the policy, fixed selection, scenario status/reasons, missingness, and
  pass/fail result. README documents the new run artifact and spec boundary.
  Focused Phase 6/7 tests pass with 109 tests, including fixed-selection,
  missingness, and holdout-isolation coverage.

## Slice 7.5 — Cohort/chain stability analysis

Measure whether results are dominated by one chain, era, liquidity band, provider, or small number of launches.

**Status:** DONE

Evidence:

- `StabilityPolicy` declares the approved subgroup dimensions, fixed-length era
  bucketing, liquidity bands, and dominance threshold as part of the immutable
  experiment specification; legacy specs default deterministically.
- `analysis/experiments/stability.py` produces discovery-only, deterministic
  chain/era/liquidity/provider and leave-one-out evidence for the already
  selected candidate. It retains sample sizes, means, concentration shares,
  explicit empty evidence, and dominance flags without changing selection or
  promotion.
- Every run persists hash-bound `stability.json`; focused Phase 7 tests cover
  holdout exclusion, concentration, policy validation, and legacy spec loading.

## Slice 7.6 — Negative controls and falsification suite

**Status:** DONE

Introduce shuffled/permuted/known-null controls designed to reveal leakage and research-process false positives.

Evidence:

- `NegativeControlPolicy` declares deterministic label-permutation and known-null
  controls as part of the content-addressed experiment specification; invalid
  methods, duplicate declarations, and invalid seeds/counts fail closed.
- The runner persists hash-bound `negative_controls.json` using the fixed
  discovery-selected candidate. Synthetic controls retain explicit method,
  scope, and missingness evidence and never alter selection, promotion, or
  sealed-holdout membership.
- Focused Phase 6/7 tests cover deterministic policy validation, fixed
  selection, known-null behavior, missingness, holdout exclusion, manifest
  linkage, and legacy spec loading. Offline fixture verification passed with
  120 tests; live-provider behavior remains outside scope and unverified.

## Slice 7.7 — Validation closure matrix

**Status:** DONE

Require replayable evidence that promoted results survive the configured robustness suite; passing remains a research result, not a profitability claim.

Exit criteria:

- Every run emits a hash-bound closure artifact that records the fixed discovery selection, promotion eligibility, each configured robustness component, and an explicit passed, failed, unavailable, or ineligible state.
- Closure cannot pass before `holdout_confirmed`; stress, uncertainty, stability, and negative-control evidence must all be complete and satisfy their declared gates.
- Repeated closure construction is deterministic, and the catalog rejects a current run with a missing closure artifact.
- README documents the closure artifact and states that a passing closure is research evidence, not a profitability claim.

Evidence:

- `analysis/experiments/closure.py` emits deterministic closure evidence for the
  fixed discovery selection. It requires `holdout_confirmed` before evaluating
  uncertainty, stress, stability, negative-control, and configured walk-forward
  components; failures and unavailable evidence remain explicit.
- The runner persists hash-bound `validation_closure.json`, and manifest
  version `phase7-run-v4` binds the closure semantics and new artifact to
  current runs while the catalog retains read-only compatibility for prior
  Phase 6/7 manifests.
- `tests/test_phase7.py` covers premature-promotion rejection, failed and
  unavailable components, deterministic replay, and walk-forward inclusion;
  Phase 3/6/7 focused verification passed with 189 tests. The locked full suite
  passed with 440 tests; byte-compilation, whitespace validation, and offline
  fixture/network-denial coverage passed. Live-provider behavior remains
  outside scope and unverified.

---

# Phase 8 — Research Product & Publication Operations

**Status:** DONE
**Depends on:** Phase 7 for claims of validated research; descriptive packages may continue under Phase 4 rules.  
**Goal:** Turn approved evidence into maintainable research products without weakening provenance or human review.

## Slice 8.1 — Review/approval history

**Status:** DONE

Represent approval, rejection, supersession, and reviewer notes as immutable records linked to exact research/package identities.

Evidence:

- `reporting/package/review_history.py` verifies immutable research runs or
  report packages, records content-addressed review decisions, enforces
  same-target supersession, and returns deterministic verified history.
- `python -m reporting.package record/show` exposes the local review-history
  boundary without changing research promotion or package publication state.
- `tests/test_phase8.py` covers verified target binding, all decision shapes,
  immutable replay, same-target supersession, and fail-closed tampering.
- Focused and full repository verification passed; live-provider behavior and
  external publication remain outside scope and unverified.

## Slice 8.2 — Rich deterministic output

**Status:** DONE

Add HTML and/or PDF only if explicitly selected, with reproducible rendering/versioning and accessibility checks.

Evidence:

- Approved handoffs now emit a deterministic, self-contained `article.html`
  artifact with escaped claims, methodology/limitations, pending-review state,
  and inline SVG charts that retain the existing chart accessibility metadata.
- Package identity includes the HTML renderer version and output-format set;
  `package-manifest.json` records both, while immutable artifact conflict and
  secret/path scanning remain unchanged. PDF remains unselected and deferred.
- `tests/test_phase4.py` covers HTML replay, missing-state preservation, and
  escaping of title/claim text. The existing Phase 4 package fixture continues
  to exercise offline approved-input generation.

## Slice 8.3 — Artifact catalog/navigation

**Status:** DONE

Provide local searchable metadata for research and report packages while preserving immutable underlying artifacts.

Evidence:

- `reporting/package/catalog.py` verifies immediate immutable research runs through
  the canonical experiment catalog and verifies report-package artifact hashes
  before exposing deterministic metadata records. Optional review-history
  summaries are read-only and remain linked to the target identity.
- `python -m reporting.package catalog` lists or case-insensitively searches
  both artifact kinds without writing catalog/index state. Invalid or tampered
  entries fail closed.
- `tests/test_phase8.py` covers deterministic replay, metadata search, no-write
  behavior, CLI JSON output, and tampered-package rejection. Focused Phase 4/8
  tests passed and the reporting guard passed; the locked full suite passed with
  447 tests, byte-compilation passed, and `git diff --check` passed.

## Slice 8.4 — Optional model-assisted drafting boundary

**Status:** DONE

An opt-in caller-supplied model may draft only editorial connective prose from an
immutable package's hash-verified claim ledger. The boundary rejects numeric,
comparative, and secret-like output, records the model and ledger identities in an
isolated immutable pending-review draft, and never changes the deterministic
article or publication/review state. `tests/test_phase8.py` covers ledger-only
model input, isolation, tamper rejection, and fact-like output rejection.

## Slice 8.5 — Publication export boundary

Create exportable packages for human publication. External posting remains a separate explicit authorization and SHOULD NOT be coupled directly to research execution.

**Status:** DONE

Evidence:

- `reporting/package/export.py` verifies the immutable source package through the
  catalog boundary, resolves effective review decisions through immutable
  supersession links, and writes a deterministic content-addressed bundle with
  source/artifact/reviewer/renderer/file hashes. It is local-only and excludes
  claim-ledger/model-draft material from publication files.
- `reporting/package/__main__.py` exposes the required JSON CLI; `tests/test_phase8.py`
  covers approval gating, deterministic replay, immutable conflicts, rejection and
  tampering, source/history isolation, draft exclusion, and CLI failure behavior.
- The locked full suite passed with 453 tests; reporting guard, byte compilation,
  and whitespace checks passed. Hosted CI remains the merge-time confirmation.

## Slice 8.6 — Publication closure matrix

**Status:** DONE

Prove source-to-claim traceability, review history, renderer replay, accessibility, secret hygiene, and supersession behavior.

Evidence:

- `docs/plans/phase-8-publication-closure-matrix.md` records the executable
  closure criteria and their evidence boundaries.
- `tests/test_phase8_closure.py::test_phase8_publication_closure` exercises the
  canonical approved handoff through deterministic package replay, claim and
  derivation traceability, SVG accessibility, immutable review supersession,
  content-addressed export replay, independent checksums, secret/path hygiene,
  and network denial.
- Focused Phase 4/8 verification, the reporting guard, byte compilation,
  whitespace checks, and the locked full repository suite passed. External
  publication and live-provider behavior remain outside scope and unverified.

---

# Phase 8R — Empirical Research Readiness

**Status:** ACTIVE
**Depends on:** Phase 8 for immutable artifacts, review history, deterministic reporting, and human-gated export.
**Goal:** Prove that the repository can produce credible, reproducible research conclusions from realistic historical crypto data before adding execution.

The central question is not merely “Does the software work?” It is whether the
system can take a meaningful crypto hypothesis from raw historical observations
to a defensible conclusion without leakage, selection bias, provenance ambiguity,
or unsupported inference. Research validity, dataset fitness, falsification, and
real-data research campaigns are first-class concerns in this phase.

## Slice 8R.1 — Dataset quality and coverage evidence

**Status:** DONE

Create the roadmap contract for deterministic dataset-profile artifacts. A
profile should describe, where applicable, dataset/content identity, asset,
provider, chain, and time-period coverage, launch-detection latency,
price/liquidity observation density, missingness, gaps, source disagreement,
censored rows, identity ambiguity, quote-conversion gaps, dead/delisted asset
retention, eligibility/exclusion reasons and distributions, and unsupported or
unavailable evidence. Experiments must bind to an exact dataset-profile identity.

The contract must distinguish dataset correctness, completeness,
representativeness, and fitness for a particular research question. No generic
quality score may replace explicit evidence.

Acceptance:

- profile identity and all applicable coverage/missingness/exclusion evidence are deterministic and replayable;
- unsupported or unavailable evidence remains explicit;
- a research input can bind to and verify the exact profile identity;
- correctness, completeness, representativeness, and question-specific fitness remain separately inspectable.

Evidence:

- `analysis/datasets/profile.py` builds a versioned, deterministic profile bound
  to the exact `DatasetSnapshot.dataset_identity`, with per-series time bounds,
  expected/observed/missing periods, internal gaps, launch-event latency,
  quote-conversion gaps, label-horizon censoring, identity checks, and explicit
  liquidity, source-disagreement, lifecycle, capability, representativeness,
  and question-fitness unavailable states where the snapshot cannot support a
  claim.
- `write_dataset_profile` writes an immutable `profile.json` under its
  content-derived profile identity and rejects conflicting rewrites. The
  `python -m analysis.datasets` command provides the read-only local entry
  point; README usage documents it.
- `tests/test_dataset_profile.py` proves deterministic replay, exact dataset
  binding, missing-period and gap accounting, explicit conversion
  unavailability, and immutable artifact replay. The focused and complete
  suites pass offline (123 focused; 458 repository-wide).

## Slice 8R.2 — Scientific benchmark corpus

**Status:** DONE

Define a deterministic synthetic or fixture-controlled corpus for offline/CI
validation of methodological behavior, not profitability. It must include a
random signal that is rejected, explicit future-data leakage that is detected or
blocked, a survivorship-biased universe, known-null permutation, known-effect
synthetic process, duplicate observations, future liquidity contamination,
insufficient sample, discovery-only overfit, unstable cross-chain/provider
results, missing conversion evidence, and ambiguous identity evidence.

Acceptance: the benchmark suite is deterministic, offline, and produces the
expected reject/block/pass behavior for each declared case.

Evidence:

- `analysis/benchmarks/` defines the versioned 12-case corpus, deterministic
  content identity, exact-result validator, and read-only CLI entry point.
- `docs/plans/phase-8r-scientific-benchmark-corpus.md` records the corpus
  contract and evidence boundary; README documents the CLI.
- `tests/test_benchmark_corpus.py` verifies the complete case set, all three
  dispositions, mismatch rejection, deterministic identity, and CLI replay.
  Focused tests, compilation, and whitespace checks pass offline. The corpus
  is methodological evidence only and does not establish alpha or execution
  readiness.

The next eligible slice is **8R.3 — Research question and hypothesis registry**.

## Slice 8R.3 — Research question and hypothesis registry

**Status:** DONE

Define durable, non-generic contracts for research questions and hypotheses.
Where applicable they must declare a stable ID, human-readable claim, universe,
treatment/signal/features, labels/outcomes, temporal availability, confounders,
baseline, minimum effect, statistical and validation policy, falsification
expectations, failure interpretation, applicable datasets, and provenance/
identity. Preserve the distinction:

`question → hypothesis → experiment specification → experiment result`.

Acceptance: identities are deterministic, declarations are sufficient to
reconstruct the intended test, and results cannot silently change the declared
question or hypothesis.

Evidence:

- `analysis/experiments/research.py` defines versioned question and hypothesis
  declarations with required universe, treatment/features, outcomes, temporal
  availability, confounders, baseline, minimum effect, statistical/validation
  policy, falsification policy, failure interpretation, applicable dataset
  identities, and provenance.
- `ResearchRegistry` validates unique question/hypothesis identities and links,
  binds compatible declarations to an `ExperimentSpec`, and causes both IDs to
  participate in the content-addressed spec and run manifest identities.
- Registry JSON is immutable and replayable; the experiment CLI validates
  individual declarations and writes registries locally without network access.
- `tests/test_research_registry.py` covers deterministic identity, linkage and
  binding, incomplete/unknown references, spec round-trip identity, immutable
  replay, and conflict rejection. Focused and repository-wide verification
  pass offline (129 focused; 466 repository-wide).

The next eligible slice is **8R.4 — Generalized falsification framework**.

## Slice 8R.4 — Generalized falsification framework

**Status:** DONE

Expand the existing negative-control and stability philosophy into a general
falsification boundary. Applicable declared tests may include label permutation,
placebo timestamps, delayed signals, shuffled identities, randomized event
times, source substitution, alternative universes, leave-chain-out,
leave-provider-out, liquidity/regime/era stratification, and robustness under
cost assumptions.

Acceptance:

- each hypothesis declares its applicable falsification policy before results are seen;
- falsification evidence is bound to the methodology and exact artifacts;
- inapplicable, unavailable, failed, and passed tests remain distinct;
- the framework does not require every test for every hypothesis or permit post-hoc selection.

Evidence:

- `analysis/experiments/spec.py` defines the versioned `FalsificationPolicy`,
  which is serialized into experiment identity and validates a unique,
  pre-result method declaration.
- `analysis/experiments/falsification.py` emits deterministic, explicit
  passed/failed/unavailable results for every declared method. Existing
  permutation/null and leave-one-out evidence is bound by artifact reference;
  unsupported methods remain unavailable and cannot be omitted after results.
- Runs include immutable `falsification.json`; `catalog.load_run` requires it
  for current manifests. `tests/test_falsification.py` proves all-method
  requirement, deterministic replay, failed/unavailable distinction, and
  invalid declaration rejection.

The next eligible slice is **8R.5 — Research campaign abstraction**.

## Slice 8R.5 — Research campaign abstraction

**Status:** DONE

Introduce a reproducible research provenance object above individual
experiments. A campaign binds the research question, dataset snapshot/profile,
hypothesis set, experiment specifications, rejected and promoted hypotheses,
validation and robustness/falsification evidence, limitations, campaign
conclusion, and exact artifact identities. A campaign is not merely a folder or
dashboard.

Acceptance: a campaign can be verified and replayed from its declared immutable
identities, including rejected hypotheses and limitations.

Evidence:

- `analysis/experiments/campaign.py` defines the versioned `ResearchCampaign`
  contract, deterministic identity, immutable artifact writer/loader, and
  verification boundary for the exact registry, dataset profile, and governed
  experiment runs. Rejected/promoted hypotheses are explicit and disjoint;
  limitations and conclusion are mandatory.
- `python -m analysis.experiments validate-campaign`, `write-campaign`, and
  `inspect-campaign` provide local campaign entry points. README usage documents
  the interface.
- `tests/test_research_campaign.py` proves deterministic identity, outcome
  validation, immutable replay, and CLI validation/writing. Focused and full
  offline verification pass.

## Slice 8R.6 — First complete real-data research campaign

**Status:** DONE

Execute at least one meaningful campaign against realistic persisted historical
data through the governed path:

`raw observations → dataset profile → question → hypotheses → discovery → validation → holdout → uncertainty → robustness/falsification → conclusion → deterministic report/package`.

The campaign may reject its hypothesis. A negative result is a successful
research outcome when the methodology behaved correctly. Alpha and profitability
are not required; explicit limitations and data-quality caveats are required.

Acceptance: the complete campaign is replayable, artifact identities and
methodology are stable, and both positive and negative conclusions can be
represented honestly without execution authority.

Implemented `execute_campaign(...)` as the governed local path: it binds
registry hypotheses to experiment specs, executes the canonical runner,
verifies the dataset profile and immutable run artifacts, and writes a stable
campaign identity. Negative outcomes are replayable, while promoted outcomes
fail closed unless holdout confirmation and validation closure both pass.

The next eligible slice is **8R.7 — Independent methodological audit**.

## Slice 8R.7 — Independent methodological audit

**Status:** BLOCKED

Close Phase 8R with an independent audit before Phase 9 may become active. The
audit must verify point-in-time and holdout integrity, deterministic identities,
dataset-profile binding, multiple-testing controls, effect-size semantics,
uncertainty, falsification completeness, provenance, reproducibility,
negative-result handling, and the absence of post-hoc methodology rewriting.

This should build upon, rather than duplicate, the repository's existing
`experiment-change-validation` workflow and any applicable
`experiment_integrity_reviewer` procedure available in the governing review
environment.

The self-review portion is complete and recorded in
[`docs/audits/phase-8r-methodological-audit.md`](docs/audits/phase-8r-methodological-audit.md):
479 repository tests pass, every reviewed contract in the audit's table is `VERIFIED` or
`UNAFFECTED`, and no demonstrated methodological-integrity violation was found. That document also
records one material completeness finding, **corrected** after this text's initial version (which
understated it): the governed runner (`analysis/experiments/runner.py`) never sets
`discovery_adjusted_p_value` on the `PromotionEvidence` it constructs, so every governed run fails
closed at `insufficient_evidence`/`MISSING_DISCOVERY_CORRECTION` — this is documented, deliberate
honesty (`tests/test_phase6.py`), not an accidental gap, and it means the governed path cannot
currently reach even `discovery_promoted`, let alone `validation_confirmed`/`holdout_confirmed`.
Separately, `target_stage` is hardcoded to `"discovery"` and never advanced to `"validation"`/
`"holdout"` even though `evaluate_candidate_promotion` implements and unit-tests both. Only
negative/rejected campaign outcomes are currently reachable end-to-end through the governed path.

`.agents/skills/experiment-change-validation`'s `REVIEWER_HANDOFF.md` requires an independent
`experiment_integrity_reviewer` verdict and is explicit that self-review does not satisfy it: *"If
the named reviewer is not configured or cannot be invoked, the parent workflow returns `BLOCKED`."*
The audit therefore terminates `BLOCKED`, not `PASS`, per that skill's own completion table. This
slice does **not** close Phase 8R. There are two distinct, independently-resolvable blockers; do
not collapse them into one:

**Blocker A — independent review unavailable.** No independent reviewer context satisfying
`.agents/skills/experiment-change-validation`'s `experiment_integrity_reviewer` contract is
currently reachable in this environment (`ListAgents` returned no such role). Resolution: (a) run
the named independent reviewer against
[`docs/audits/phase-8r-methodological-audit.md`](docs/audits/phase-8r-methodological-audit.md)
(§8 of that document is the exact handoff instruction for that reviewer) when the role becomes
available and record its verdict here, or (b) an explicit, documented repository-authority decision
to accept an alternative review path.

**Blocker B — material audit finding (corrected).** Governed campaign execution
(`analysis/experiments/runner.py:run_experiment`, called from `campaign.py:execute_campaign`) lacks
an authorized, provenance-bound source of discovery/confirmation significance evidence.
`run_experiment` never sets `PromotionEvidence.discovery_adjusted_p_value`, so
`evaluate_candidate_promotion` fails closed at `insufficient_evidence`/`MISSING_DISCOVERY_CORRECTION`
before a run can ever reach `discovery_promoted` — this is documented, deliberate fail-closed
behavior (`tests/test_phase6.py`'s `test_runner_executes_the_declared_sequence_and_honestly_withholds_significance`),
not a defect in itself. The already-implemented BH/Holm correction machinery
(`analysis/experiments/hypotheses.py`'s `evaluate_hypothesis_family`) is never invoked from the
governed path because nothing computes or supplies a raw p-value for it to correct.
`target_stage` is also, separately, hardcoded to `"discovery"` and never advanced to
`"validation"`/`"holdout"`, even though `evaluate_candidate_promotion` implements and unit-tests
both later stages (`analysis/alpha/evaluation.py`). Consequently, an end-to-end governed positive
promotion path is currently unreachable beginning at the discovery gate — see the audit's §4 for
the full correction. Resolution: the dependency-ordered Slice 8R.7a → 8R.7b → 8R.7c chain below.

Neither blocker resolves the other: an independent `PASS` verdict on the current methodology does
not make Blocker B disappear, and fixing Blocker B does not by itself satisfy Blocker A. Phase 8R
closes only when both are resolved.

### Next remediation slices: 8R.7a → 8R.7b → 8R.7c

None of these are implemented in this documentation slice (scope discipline). They are
dependency-ordered: 8R.7b cannot be usefully implemented before 8R.7a's contract is decided, and
8R.7c's positive-outcome fixture depends on both. A prior version of this roadmap entry described a
single "8R.7a — governed validation/holdout promotion" slice; that description assumed
`discovery_promoted` was already reachable, which the corrected audit finding (§4 of
`docs/audits/phase-8r-methodological-audit.md`) shows is false. It is replaced by the three slices
below.

**Current statistical responsibility map** (established by this reconciliation, not assumed):

- Raw p-value computation: **owned by nobody today.** No component computes or accepts a raw
  significance p-value for a candidate. `ExperimentSpec` (`analysis/experiments/spec.py`) is purely
  declarative and has no p-value/statistical-test-identity field.
- Multiple-testing correction: owned by `analysis/experiments/hypotheses.py`'s
  `evaluate_hypothesis_family`, which takes a caller-supplied raw-p-value map keyed to the exact
  frozen family (`freeze_hypothesis_family`) and applies BH/FDR (`stage="discovery"`) or
  Holm-Bonferroni (`stage="confirmation"`) — implemented and tested, but never called from the
  governed path.
- Discovery vs. confirmation use different correction policies: yes —
  `HypothesisFamily.discovery_correction`/`discovery_q` vs. `confirmation_correction`/
  `confirmation_alpha` (`spec.py`), matching `PromotionPolicy`'s equivalent fields
  (`evaluation.py`). `evaluate_candidate_promotion`'s `"holdout"` stage consumes
  `holdout_adjusted_p_value` against `confirmation_alpha` — i.e. holdout uses the *confirmation*
  correction, not a third policy. `"validation"` uses no p-value at all, only the boolean
  `validation_replicated`/`validation_semantics_frozen` fields — the repository does not currently
  define a validation-stage correction; preserve that rather than inventing a symmetric one.
- Frozen hypothesis-family membership: represented by `FrozenHypothesisFamily`/`HypothesisIdentity`
  (`hypotheses.py`), keyed by `feature`/`threshold`/`horizon`/`subgroup`/`model_specification`, with
  a content-derived `family_id`. `run_experiment` already freezes this per run
  (`hypothesis_family.json`) but never evaluates it.
- Stage-specific raw p-value provenance type: **does not exist.** No dataclass or artifact records
  which statistical test produced a raw p-value, its parameters, or its seed.
- p-values in immutable identities/artifacts today: none — `hypothesis_family.json` records only the
  frozen grid and correction policy, not any evaluated p-value; `promotion.json` records whatever
  `PromotionEvidence` was passed in (currently always `discovery_adjusted_p_value: null`).
- Whether externally-supplied significance evidence needs a schema/manifest/version change: likely
  yes at the `ExperimentSpec`/`run_experiment` boundary (a new declarative or input field) and
  possibly `MANIFEST_VERSION` (`runner.py`, currently `"phase8r-run-v1"`), since the run's content
  identity would gain a new semantically-relevant input; this is a design question for 8R.7a, not
  answered here.
- Whether computing empirical p-values inside the runner would violate the runner/orchestration
  boundary: `AGENTS.md`'s `analysis/` scope requires point-in-time-safe, non-fabricating research
  logic; `runner.py`'s own module docstring says it "never redefines cohort, feature, label, split,
  or candidate-evaluation semantics." Introducing a concrete significance test inside `runner.py`
  would be new research logic, not orchestration — this is a real design tension for 8R.7a's
  candidate B below, not resolved here.

**Slice 8R.7a — Significance-evidence contract.** **Status: DONE (contract only; Blocker B is
NOT resolved).** Candidate A (externally supplied raw significance evidence) is adopted.
`analysis/experiments/significance.py` defines `SignificanceEvidence` (one caller-supplied raw
p-value per frozen hypothesis, content-addressed as `evidence_id`, carrying hypothesis identity,
frozen `family_id`, `experiment_spec_id`, `dataset_version`, `stage` (`discovery`/`confirmation`
only — no invented validation-stage p-value), `raw_p_value`, `statistical_test`/`test_version`
identity, an `observed_through` temporal boundary, `parameters`, an optional non-negative `seed`,
and a required `provenance` string) and `SignificanceEvidenceBundle`
(`build_significance_evidence_bundle`), which validates a caller-supplied entry set against one
`FrozenHypothesisFamily` before exposing `raw_p_values()` — the exact `Mapping[str, float | None]`
shape `evaluate_hypothesis_family` (`hypotheses.py`) already consumes. The frozen-family identity
check itself was extracted into `hypotheses.verify_frozen_family_identity` and reused by both
`evaluate_hypothesis_family` and the new bundle validator rather than duplicated. Fail-closed
cases covered by `tests/test_phase8r_significance.py`: non-finite/out-of-range p-values, an
unsupported stage, missing/incomplete family evidence, evidence for a hypothesis outside the
frozen family, duplicate/conflicting evidence for one hypothesis, and evidence bound to the wrong
dataset version, hypothesis family, or experiment spec. `runner.py`/`campaign.py` are unchanged —
this evidence is not wired into governed execution, `PromotionEvidence.discovery_adjusted_p_value`
is still never set by `run_experiment`, and `MISSING_DISCOVERY_CORRECTION` fail-closed behavior is
unchanged (`tests/test_phase6.py`). No multiple-testing correction is implemented or duplicated
here. Manifest identity: this evidence is observed result data, not pre-registered methodology, so
it deliberately does not join `ExperimentSpec.spec_version` or `runner.py`'s `MANIFEST_VERSION`;
it versions its own identity (`SIGNIFICANCE_MANIFEST_VERSION = "phase8r-significance-evidence-v1"`).
Whether run/campaign identity must absorb this evidence once it is actually consumed is deferred to
8R.7b, which is where that consumption happens. Blocker B is unchanged by this slice — the
governed path still cannot reach `discovery_promoted` — and remains open pending 8R.7b/8R.7c.

The remainder of this entry is the original pre-implementation design record; it is retained for
context on the two candidates considered and the questions this slice had to answer. Candidate A
was selected; Candidate B was not implemented and remains available to a future slice if Candidate
A's approach is later found insufficient.

Original scope: define the governed contract by which
statistically meaningful raw significance evidence enters experiment execution, before any
implementation. Must answer: source of raw p-values (caller-supplied vs. internally computed);
stage association (discovery vs. confirmation/holdout; validation's status given no existing
p-value field); hypothesis association (must key to `HypothesisIdentity`, matching
`freeze_hypothesis_family`'s exact-membership contract); dataset/campaign association; statistical-
test identity and parameters/seed where applicable; provenance representation; explicit
missing/unavailable behavior (must stay `insufficient_evidence`, never a fabricated default);
deterministic-identity implications (does the raw evidence or its test identity become part of run
identity, and does `MANIFEST_VERSION` need to change); and compatibility with the existing frozen
hypothesis-family machinery. Document at least these two candidates without selecting one absent a
repository-authority decision:

- **Candidate A — externally supplied raw p-values.** The caller supplies raw statistical evidence;
  the governed experiment layer validates provenance/family membership and performs the existing
  correction via `evaluate_hypothesis_family`. Matches the current separation of responsibilities
  (correction is already externalized from raw-evidence computation) and does not make the runner
  invent a new statistical test. Open questions: caller trust/provenance verification, binding test
  identity and parameters into the run's content identity, preventing arbitrary post-hoc p-value
  selection, and whether validation needs an analogous externally-supplied contract for
  `validation_replicated`/`validation_semantics_frozen`.
- **Candidate B — repository-computed empirical significance.** A declared statistical method
  (potentially permutation-based, reusing `negative_controls.py`'s existing label-shuffle
  machinery, e.g. an empirical p-value = fraction of permuted-label differences at or above the
  observed difference) computes raw p-values inside an appropriate methodological component.
  Stronger end-to-end reproducibility, but introduces a substantive statistical methodology into the
  governed path for the first time; needs an explicit test definition and stated assumptions; must
  not casually reuse `negative_controls.py`'s machinery if permutation-based falsification and
  permutation-based inferential significance testing turn out to have different required semantics
  (they answer different questions — "would this look different under the null" vs. "is this
  difference statistically significant" — even though both shuffle labels); and, given its
  research-integrity weight, likely requires its own `experiment_integrity_reviewer` pass before
  being wired into the governed path.

No statistical methodology is selected or implemented by this roadmap entry.

**Slice 8R.7b — Frozen-family correction integration.** **Status: DONE (focused evidence:
`tests/test_phase8r_significance.py`, 141 passed with `tests/test_phase6.py`).** `run_experiment`
accepts a validated `SignificanceEvidenceBundle`, revalidates its frozen-family/spec/dataset/stage
bindings, feeds its complete raw p-value map only through `evaluate_hypothesis_family`, and binds
the candidate's matching corrected value to `PromotionEvidence` for discovery evidence only.
Confirmation evidence is persisted and corrected but cannot satisfy discovery. Raw evidence and its
corrected evaluation are immutable run artifacts, and evidence identity participates in run identity;
omitted or unavailable p-values remain fail-closed. Mixed observation boundaries and ambiguous
candidate-to-hypothesis mappings fail closed. The next slice is 8R.7c.

Original scope: wire
authorized raw significance evidence into the existing `freeze_hypothesis_family`/
`evaluate_hypothesis_family` machinery so the governed path obtains corrected discovery/confirmation
values only through the repository's already-declared family/correction semantics — never by
computing a corrected value ad hoc. Requires tests proving: exact family membership is enforced
(missing/extra hypothesis evidence fails closed, per `hypotheses.py:121-127`'s existing contract);
correction is deterministic; corrected values are provenance-bound (traceable to the raw evidence
and test identity that produced them); and methodology-significant evidence participates in run/
artifact identity where the 8R.7a design requires it.

**Slice 8R.7c — Sequential governed promotion.** Only after significance evidence can legitimately
satisfy discovery should `run_experiment`/`execute_campaign` advance the frozen candidate through
`discovery` → `validation` → `holdout` using the existing, unmodified `evaluate_candidate_promotion`
API and `target_stage` contract (`analysis/alpha/evaluation.py`). Requires: a successful positive
fixture reaching `holdout_confirmed` end-to-end through `execute_campaign`/`verify_campaign`; a
discovery-failure case; a validation-failure case; a holdout-failure case; frozen candidate identity
preserved across stages (no re-selection); no validation/holdout reselection from later-partition
data; sealed-holdout isolation preserved (`SplitResult.sealed`, `build_split`); and deterministic
replay. If the repository's actual promotion contract does not require a validation-stage p-value
(as observed above — `PromotionEvidence` has no such field), preserve that asymmetry rather than
inventing one for symmetry with discovery/holdout.

Each of 8R.7a/8R.7b/8R.7c that changes promotion, correction, or run/campaign identity semantics
MUST be run through `.agents/skills/experiment-change-validation` before merge, including
temporal/holdout boundary re-verification (that skill's §3) once holdout data becomes newly consumed
by the governed path. After implementation, `experiment_integrity_reviewer` should be invoked per
that skill's §6; if still unavailable, report `BLOCKED` rather than self-certifying the remediation,
consistent with how the 8R.7 audit itself was handled.

## Phase 8R exit criteria

Phase 8R is complete only when:

- deterministic dataset-quality evidence exists;
- the scientific benchmark corpus passes;
- questions and hypotheses have durable identities;
- falsification evidence is methodology-bound;
- a research campaign can be replayed;
- at least one realistic campaign completes end-to-end;
- positive and negative outcomes are represented honestly;
- independent methodological review passes; and
- no research success implies execution authority.

---

# Phase 9 — Paper / Forward Execution

**Status:** DEFERRED

Phase 9 remains execution-free-of-real-capital and requires a separate explicit
activation decision. Successful Phase 8R closure is a prerequisite. Its purpose
is forward validation of already-established research, not a new place to search
for alpha.

If activated, the design must address timestamped signal generation from only
contemporaneously available evidence, paper order creation, realistic fill
simulation/observation, market impact and slippage, latency, rejected or
unfilled orders, portfolio state, risk limits, execution provenance, comparison
of backtest assumptions with forward behavior, drift detection, strategy
disablement, and human review.

Phase 9 must not silently modify hypothesis methodology based on forward
performance. Forward evidence may trigger a new research campaign, but it must
not mutate historical experiment identity.

---

# Phase 10 — Live Execution

**Status:** DEFERRED

Phase 10 is a distinct product and safety boundary, not an automatic continuation
of Phase 9. It remains deferred unless separately authorized by an explicit
product decision.

Separate design work must address real capital, exchange authentication,
wallet/custody boundaries, secrets, order authorization, position/risk limits,
emergency stop, reconciliation, idempotent execution and retries,
external-system failure, audit trail, operator approval, disaster recovery,
live monitoring, and applicable legal/regulatory considerations. Phase 10
activation requires that separate decision and safety evidence.

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

The current frontier is **Phase 8R empirical research readiness**. Phase 8 is
complete. Phase 9 remains deferred pending Phase 8R closure and an explicit
activation decision; Phase 10 remains separately deferred and requires its own
product decision. No roadmap phase authorizes paper or live execution.

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

Slice 6.5 is DONE. `analysis/experiments/catalog.py` verifies immutable run
manifests, identities, and artifact hashes before returning deterministic
read-only catalog records. Its comparison boundary requires matching feature
and label sets, explicit registry-approved version compatibility, and equality
of all other methodology fields before it returns candidate summary deltas;
invalid, tampered, and methodologically incompatible runs fail closed.

Slice 6.6 is DONE. `analysis/experiments/control.py` and
`python -m analysis.experiments` expose validate, run, verified inspect, and
explicit approval operations by composing the existing spec, runner, and catalog
contracts. Approval is a separate immutable human attestation over a hash-verified
run and cannot alter promotion or holdout state.

Slice 6.7 is DONE. `docs/plans/phase-6-experiment-control-closure-matrix.md`
and `tests/test_phase6_closure.py` close Phase 6 with composed offline evidence:
public-spec reconstruction and identical replay, complete manifest/hash
verification, frozen-family retention, sealed holdout isolation from discovery
scoring/promotion, and rejection of a methodologically incompatible comparison.
This evidence does not claim alpha, profitability, live-provider acceptance, or
production-scale sample adequacy.

Slice 7.1 is DONE. `SplitPolicy` now opts explicitly into deterministic purged
walk-forward evaluation; the runner learns selection thresholds only from each
expanding training window, scores the following non-overlapping validation
window, retains every fold's membership/removal/result evidence, and never
passes the final sealed holdout into fold scoring.

Slice 7.2 is DONE. `UncertaintyPolicy` now declares the approved deterministic
moving-block bootstrap, and each run retains method/configuration identity plus
the selected-candidate observation scope in `uncertainty.json`. Unsupported
dependence structures and insufficient observations remain explicit rather than
being imputed.
