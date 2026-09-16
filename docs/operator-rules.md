# Operator Rules

## Purpose

This report is the repository-local inventory of rules that govern a human operator or invoking
agent. It records both normative instructions and behavior that current executables enforce. It
does not promote roadmap proposals into current rules, and it does not imply that fixture success
proves live-provider reliability, profitable research, publication approval, or production fitness.

## Scope

The map covers repository use from local setup and provider-backed ingestion through canonical
storage, offline Phase 2/3 research, Phase 4 review-package generation, monitoring, recovery,
development, Git, review, and verification. “HARD” means the cited executable rejects or constrains
the operation when that path is used; it does **not** mean every possible alternate path is blocked.
“SOFT” means prose/convention only. “PARTIAL” means enforcement exists on only some paths or relies
on an operator invoking a guard. “UNKNOWN” is reserved for rules whose effective status cannot be
established from the landed repository.

Roadmap items after the current frontier are not operative merely because they are described. In
particular, no experiment CLI, publication pipeline, paper/live execution system, release workflow,
or hosted deployment exists. Absence of such a path is reported as scope, not as an implemented
authorization service.

## Sources Examined

* Active instructions: root `AGENTS.md` (no nested `AGENTS.md` or `AGENTS.override.md` exists).
* Operator/contributor material: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`,
  `ROADMAP.md`, `docs/RUNBOOK.md`, `docs/ARCHITECTURE.md`, `docs/durable-invariants.md`,
  `docs/architectural-constraints.md`, `docs/verification-expectations.md`, and
  `docs/engineering/version-control.md`.
* Phase contracts/records: every tracked file under `docs/plans/`, with accepted Phase 3 decisions,
  Phase 4 implementation decisions, and acceptance matrices treated above aspirational plan text.
* Executable/configuration surfaces: `pyproject.toml`, `uv.lock`, `.env.example`, all four
  `config/*.yaml` files, `.github/workflows/ci.yml`, `scripts/run-tests*`, all Python modules under
  `ingestion/`, `storage/`, `normalization/`, `scheduler/`, `analysis/`, and `reporting/`.
* Enforcement evidence: all tracked `tests/test_*.py`; storage/reporting/provider skill guards and
  their self-tests under `.agents/skills/`; the one-slice Git scripts/tests; CLI parsers, validators,
  schema constraints, state transitions, retry loops, redaction, and output checks.
* Repository state/history: tracked-file inventory, current Git status/diff, recent commits, and
  searches for normative language, network imports, schema writers, hooks, CI/release configuration,
  and alternate data stores. History was not needed to override current semantics.

## Rule Precedence

The repository explicitly establishes this order for phase work: (1) active user goal, (2) checked-in
active phase specification, (3) implemented code/tests/storage/manifests/configuration from completed
phases, and (4) the Phase 1 storage contract (`AGENTS.md`, **Sources of truth**). The active user also
requires the complete applicable instruction chain. `AGENTS.override.md` would replace same-directory
`AGENTS.md`, and deeper instructions would be more specific, but neither exists here.

`docs/engineering/version-control.md` separately yields to more-specific repository instructions,
forge controls, and explicit operator instructions. `CONTRIBUTING.md` and `SUPPORT.md` say executable
behavior and active requirements outrank stale plans/examples. Where these rules do not establish a
winner, this report says **UNRESOLVED** rather than manufacturing precedence.

## Operator Rule Matrix

| ID | Rule | Type | Applies To | Enforcement | Source | Failure/Block Condition |
|---|---|---|---|---|---|---|
| OPR-001 | Follow the active instruction/source precedence; report conflicts. | MUST | Agent/contributor | SOFT | `AGENTS.md` — Instruction scope; Sources of truth | Unreviewable or noncompliant change |
| OPR-002 | Work only the active, smallest coherent phase slice in dependency order. | MUST | Phase work | SOFT | `AGENTS.md` — Sequential execution; `ROADMAP.md` §1 | Completion claim invalid |
| OPR-003 | Inspect and preserve existing Git state; avoid destructive cleanup. | MUST NOT | Git operator/agent | SOFT | `docs/engineering/version-control.md` §§0.2, 8 | Work loss/conflict; stop and report |
| OPR-004 | Use the selected branch; branch/remote operations require a task/workflow need. | CONDITIONAL | Git operator/agent | SOFT | version-control §§0.1, 0.3, 4.2 | Remote step not authorized or BLOCKED |
| OPR-005 | Commit coherent intended changes only; never rewrite shared history routinely. | MUST | Git operator/agent | SOFT | version-control §§3–4 | Review/provenance violation |
| OPR-006 | Use a narrow PR and do not bypass review/protection rules. | MUST | Contributor/remote operator | SOFT | `CONTRIBUTING.md` — Pull requests; version-control §5 | Review gate not satisfied |
| OPR-007 | Use Python 3.10+ and pinned/locked dependencies. | MUST | Local/CI environment | PARTIAL | `pyproject.toml`; CI workflow; `README.md` Quickstart | Install/CI/test failure |
| OPR-008 | Configure only intended provider paths through env/YAML; keep credentials untracked. | MUST | Ingestion operator | PARTIAL | `.env.example`; `docs/RUNBOOK.md` Environment contract | Path skipped, auth error, or disclosure |
| OPR-009 | Never expose secrets; privately report and rotate suspected exposures. | MUST NOT | Every operator/output | PARTIAL | `SECURITY.md`; `storage.db.safe_error_message`; package scanner | Redaction/rejection, credential rotation |
| OPR-010 | Initialize and use canonical DuckDB/Parquet storage. | MUST | Pipeline operator | HARD | `storage.__main__.main`; `storage.schema.initialize` | Initialization/schema error |
| OPR-011 | Storage migrations must be canonical, versioned, sequential, idempotent, and tested. | MUST | Schema maintainer | PARTIAL | `AGENTS.md`; storage skill; `storage.schema.initialize` | Newer schema rejected; CI/test failure |
| OPR-012 | Treat DuckDB as authoritative and repair Parquet drift mechanically. | MUST | Recovery operator | HARD | `storage.__main__.main`; `storage.db.verify/repair_parquet_publication` | Divergence reported/rebuilt |
| OPR-013 | Do not delete persisted stores while jobs run; avoid concurrent writer processes. | MUST NOT | Runtime operator | PARTIAL | `docs/RUNBOOK.md` Data safety; scheduler locking | Data loss or DuckDB lock errors |
| OPR-014 | Keep all provider/network access in ingestion; analysis/reporting remain offline/local. | MUST NOT | Developer/phase operator | PARTIAL | `AGENTS.md`; offline tests; reporting guard | Fixture/guard failure when exercised |
| OPR-015 | Preserve canonical address-scoped identity; never reconcile by symbol alone. | MUST | Data/research operator | HARD | `normalization.reconcile_assets`; snapshot validators | Ambiguous/unknown identity rejected or unlinked |
| OPR-016 | Preserve timestamps, missingness, point-in-time visibility, ordering, and provenance. | MUST | Analysis/research operator | HARD | `DatasetSnapshot`; Phase 2/3 validators/tests | `ValueError` / leakage gate failure |
| OPR-017 | Run CEX backfill with required market arguments; checkpointed reruns are idempotent. | MUST | Backfill invocation | HARD | `ingestion.cex.backfill.main/backfill_symbol` | argparse/config/market error |
| OPR-018 | Respect provider routing, capabilities, rate limits, and bounded retry semantics. | MUST | Ingestion operator/developer | HARD | provider clients/config; capability types | Explicit unsupported/unavailable/error |
| OPR-019 | Missing EVM/Solana credentials skip scheduler paths; direct paths may reject them. | CONDITIONAL | Scheduler/direct listener | HARD | `Pipeline.evm_listeners/solana_listener`; provider clients | Skip or credential/RPC error |
| OPR-020 | Cursor/continuation updates must be monotonic/CAS-safe; incomplete scans fail closed. | MUST | Ingestion runtime/operator | HARD | storage cursor accessors; EVM/Solana listeners | Conflict/range/continuation error |
| OPR-021 | Scheduler cycles execute the fixed job order and isolate recorded failures. | MUST | Scheduler operator | HARD | `Pipeline.run_cycle/run_job` | Failed status stored; later jobs continue |
| OPR-022 | Continuous scheduling prevents overlap and clamps Tier 0 cadence to 15–30 minutes. | MUST | Continuous scheduler | HARD | `Pipeline.expected_job_intervals`; `build_scheduler` | Library skips/coalesces overlap |
| OPR-023 | Monitor run health and inspect/retry the smallest failed boundary. | SHOULD | Operations | SOFT | `docs/RUNBOOK.md` Monitor/Debugging; `scheduler.status` | Failure remains unnoticed/unrecovered |
| OPR-024 | Use the configured deterministic next-bar-open, long-only CEX simulator policies. | MUST | Phase 2 caller | HARD | `BacktestConfig.validate`; `simulate` | Unsupported input raises/rejects/skips |
| OPR-025 | Strategies emit intentions only; simulator owns fills, cash, fees, and positions. | MUST NOT | Strategy author | HARD | Strategy protocol; simulator ledger | No strategy mutation channel; invalid target rejected |
| OPR-026 | Phase 2 runs/metrics must use canonical ledgers and reproducible manifests. | MUST | Phase 2 operator | HARD | run artifact writer; metrics validators; tests | Invalid/empty ledger or artifact error |
| OPR-027 | Phase 3 must be cohort-first with explicit eligibility/exclusion evidence. | MUST | Research operator | HARD | cohort/eligibility modules; tests | Ineligible row excluded with reason |
| OPR-028 | Phase 3 labels, feature policies, splits, and identities must use registered temporal contracts. | MUST | Research/experiment operator | HARD | alpha registry/labels/split; experiment spec | Unknown/incompatible declaration rejected |
| OPR-029 | Promotion must follow the discovery→validation→holdout state machine and evidence gates. | MUST | Research operator | HARD | `evaluate_candidate_promotion`; promotion tests | Candidate remains/reverts to rejected stage |
| OPR-030 | Experiment specs/runs must be declarative, content-addressed, local, and immutable. | MUST | Phase 6 caller | HARD | `ExperimentSpec`; `run_experiment` | Validation error or conflicting artifact rejection |
| OPR-031 | Never claim alpha/profitability/production readiness or authorize trading from research tests. | MUST NOT | Operator/reporter | SOFT | `AGENTS.md`; `SECURITY.md`; handoff flags | Scope/review violation |
| OPR-032 | Phase 4 accepts only immutable, hash-verified, approved, reviewer-attributed handoffs. | MUST | Package generator caller | HARD | `validate_approved_handoff`; `generate_package` | `ValueError` before generation |
| OPR-033 | Every factual/numeric/comparative claim must resolve and derive from approved evidence. | MUST | Report author/generator | HARD | `validate_claims` | Claim validation fails |
| OPR-034 | Charts must use staged evidence, approved transforms, explicit missingness, units, provenance, and accessibility metadata. | MUST | Chart/package caller | HARD | `validate_chart`; static renderer/a11y validator | Chart/render validation fails |
| OPR-035 | Generated packages remain pending human-review artifacts and must not publish. | MUST NOT | Phase 4 operator | PARTIAL | package output flags; `AGENTS.md` | No repository publication path; human gate external |
| OPR-036 | Run focused checks then the repository test/compile/whitespace gates and report truthfully. | MUST | Contributor/agent | PARTIAL | `CONTRIBUTING.md`; CI workflow; test wrappers | CI/check failure or unverified completion |
| OPR-037 | Unit/fixture tests must avoid live providers; live acceptance requires separate prerequisites/evidence. | MUST | Test/live-check operator | PARTIAL | runbook; CI scan; socket-denial tests | CI failure or `UNVERIFIED_RUNTIME` |
| OPR-038 | Security testing must be authorized, fixture-based, and non-abusive. | MUST NOT | Security tester | SOFT | `SECURITY.md` Safe testing | Stop/report privately; third-party authorization needed |

## Detailed Rules

### OPR-001 — Instruction and evidence precedence
**Rule:** Follow the applicable instruction chain and evidence hierarchy; surface conflicts instead
of silently resolving them.
**Type:** MUST.
**Applies to:** Agents and contributors.
**Trigger / Preconditions:** Any repository task, especially a phase or storage task.
**Required behavior:** Read active instructions and the applicable accepted specification; prefer
current executable behavior/configuration over stale prose.
**Prohibited behavior:** Reconstruct missing decisions from memory or silently overwrite an
implemented contract.
**Failure result:** The task is noncompliant; an unresolved conflict must be reported.
**Enforcement:** Instruction/review discipline. **Enforcement strength:** SOFT.
**Source of truth:** `AGENTS.md` headings **Instruction scope** and **Sources of truth**.
**Evidence:** `CONTRIBUTING.md` **Before you start** and `SUPPORT.md` **Start with the repository
documentation** repeat that implementation and active requirements outrank stale plans.
**Exceptions / Overrides:** Active user instructions and a more-specific applicable instruction;
same-directory `AGENTS.override.md` would replace `AGENTS.md` (none exists).
**Related rules:** OPR-002, OPR-036.
**Notes:** The precedence between two equally specific conflicting runtime paths is UNRESOLVED until
repository evidence establishes it.

### OPR-002 — Sequential, one-slice work
**Rule:** Advance only the active phase or named smallest coherent slice, in dependency order.
**Type:** MUST. **Applies to:** Phase maintainers/agents.
**Trigger / Preconditions:** Implementation or roadmap maintenance.
**Required behavior:** Inspect prior contracts, select the first incomplete unblocked slice unless the
operator names another, test it, and stop for review.
**Prohibited behavior:** Pull later-phase deliverables forward, silently choose open decisions, or mark
a roadmap-only edit DONE.
**Failure result:** Completion/DONE claim is invalid.
**Enforcement:** Review and roadmap convention. **Enforcement strength:** SOFT.
**Source of truth:** `AGENTS.md` **Sequential phase execution** and **Phase-specific execution order**;
`ROADMAP.md` §§1.1–1.3 and **Roadmap maintenance contract**.
**Evidence:** `ROADMAP.md` identifies Slice 6.4 as the current frontier and requires DONE/ACTIVE/evidence
updates only after landing.
**Exceptions / Overrides:** An explicitly narrower/different active user target.
**Related rules:** OPR-001, OPR-036. **Notes:** Later roadmap slices are plans, not current commands.

### OPR-003 — Preserve Git/worktree/index state
**Rule:** Inspect and preserve unrelated working-tree, index, and commit state.
**Type:** MUST / MUST NOT. **Applies to:** Git operator/agent.
**Trigger / Preconditions:** Before editing, staging, recovery, or committing.
**Required behavior:** Inspect status, branch, unstaged and staged diffs; stage intended paths explicitly.
**Prohibited behavior:** Routine `reset --hard`, `clean -fd`, checkout-discard, history rewrite, or cleanup
that absorbs/discards unrelated work.
**Failure result:** Stop and report material overlap rather than destroy work.
**Enforcement:** Process policy only. **Enforcement strength:** SOFT.
**Source of truth:** `docs/engineering/version-control.md` §§0.2, 4, 8 and Appendix A.
**Evidence:** The policy explicitly says a dirty tree is not itself blocking.
**Exceptions / Overrides:** Explicit, target-confirmed recovery authority; still preserve an audit trail.
**Related rules:** OPR-004–006. **Notes:** No pre-commit hook enforces this.

### OPR-004 — Branch and remote-operation authority
**Rule:** Use the operator-selected branch; do not make local completion depend on remotes, branch
changes, signing, or forge actions unless the task/workflow requires them.
**Type:** CONDITIONAL. **Applies to:** Git/forge operator.
**Trigger / Preconditions:** Branch, fetch/pull/push, signing, PR, or forge-setting operation.
**Required behavior:** Use local-first, non-interactive operations and perform remote actions only when
requested and authorized.
**Prohibited behavior:** Creating/switching/rebasing solely for generic policy; changing global Git or
forge protection settings; guessing through destructive conflicts.
**Failure result:** Complete safe local work and mark remote/signing action BLOCKED or NOT RUN.
**Enforcement:** Policy. **Enforcement strength:** SOFT.
**Source of truth:** version-control §§0.1, 0.3, 4.2, 6, 11–12.
**Evidence:** Appendix B explicitly permits continued local work on `main` and without network/`gh`.
**Exceptions / Overrides:** Explicit task or repository/remote workflow requirement.
**Related rules:** OPR-003, OPR-006. **Notes:** Actual remote protection configuration is absent and
therefore UNRESOLVED.

### OPR-005 — Commit and history discipline
**Rule:** Commit one coherent, verified boundary using existing identity; do not rewrite shared history.
**Type:** MUST. **Applies to:** Committer.
**Trigger / Preconditions:** A task/operator/harness requires a commit.
**Required behavior:** Stage only intended paths; prefer Conventional Commits when no stronger convention;
use existing Git identity and truthful attribution.
**Prohibited behavior:** Secrets, ignored runtime output, invented authors/issues/co-author trailers,
routine amend/rebase/force push, or moving published tags.
**Failure result:** Unreviewable/unsafe history; use additive `git revert` for shared bad commits.
**Enforcement:** Policy and `.gitignore` assistance. **Enforcement strength:** SOFT.
**Source of truth:** version-control §§0.4, 3–4, 7–10.
**Evidence:** §4.3 permits only explicitly authorized unprotected-branch rewriting and prefers
`--force-with-lease`, never plain `--force`.
**Exceptions / Overrides:** Explicit authorization for current-task unshared commits or recovery.
**Related rules:** OPR-003, OPR-009. **Notes:** `.gitignore` is not a secret or content gate.

### OPR-006 — Pull-request and review contract
**Rule:** Normal development uses a focused PR; its description must state behavior, phase/boundaries,
impact, exact verification, replay/offline evidence, risks, and unresolved checks.
**Type:** MUST. **Applies to:** Contributor/remote operator.
**Trigger / Preconditions:** Opening/reviewing/merging a PR.
**Required behavior:** Preserve actual required checks/reviewers/protections and select the configured
merge strategy; prefer squash when process commits add no semantic boundary.
**Prohibited behavior:** Normal direct push to `main`, fabricated approval, dismissed required reviewer,
protection bypass, unauthorized merge/auto-merge setting change, or force-push without authority.
**Failure result:** Review/merge gate remains unsatisfied.
**Enforcement:** Documentation only; no CODEOWNERS or ruleset-as-code. **Enforcement strength:** SOFT.
**Source of truth:** `CONTRIBUTING.md` **Development workflow/Pull requests**; version-control §5.
**Evidence:** `.github/workflows/ci.yml` runs on PR and `main` pushes but does not prove branch protection.
**Exceptions / Overrides:** PR creation itself is conditional unless explicitly requested; actual forge
rules prevail.
**Related rules:** OPR-004, OPR-036. **Notes:** Required approval count/status-check enforcement is UNRESOLVED.

### OPR-007 — Supported Python and locked environment
**Rule:** Operate with Python 3.10+ and resolve dependencies from the pinned manifest/lock.
**Type:** MUST. **Applies to:** Local setup and CI.
**Trigger / Preconditions:** Installation/testing.
**Required behavior:** Install the project; use `uv sync --locked --extra test` where provisioning the
locked test environment and `--no-sync` only after provisioning.
**Prohibited behavior:** Ad hoc/global dependency installation to evade an unavailable gate.
**Failure result:** Import/install/test or CI failure.
**Enforcement:** Package metadata and CI lock synchronization. **Enforcement strength:** PARTIAL.
**Source of truth:** `pyproject.toml` `requires-python`/pins; `uv.lock`; CI install step.
**Evidence:** `tests/test_ci.py` pins the CI setup and test dependency expectations.
**Exceptions / Overrides:** Test wrappers may reuse `CCXT_PROJECT_VENV`; host Python may supply pytest while
the venv supplies project dependencies.
**Related rules:** OPR-036. **Notes:** CI tests 3.12 only, so runtime compatibility of 3.10/3.11 is UNRESOLVED.

### OPR-008 — Provider configuration and credential scope
**Rule:** Put provider credentials/RPC URLs only in documented environment variables and enable only the
paths intentionally run.
**Type:** MUST. **Applies to:** Ingestion operator.
**Trigger / Preconditions:** Live provider use.
**Required behavior:** Copy `.env.example` locally, review YAML routes/defaults, and independently configure
RPC observation versus explorer enrichment.
**Prohibited behavior:** Committing `.env`, hardcoding/printing credentials, or assuming an explorer key
substitutes for RPC.
**Failure result:** Scheduler skip, direct credential/RPC error, provider authentication failure, or leak.
**Enforcement:** Env reads, route configuration, `.gitignore`, provider errors. **Enforcement strength:** PARTIAL.
**Source of truth:** `.env.example`; `config/chains.yaml`, `evm.yaml`, `solana.yaml`; runbook **Environment contract**.
**Evidence:** `Pipeline` checks configured EVM RPC env names and Helius key before scheduling those paths.
**Exceptions / Overrides:** Routescan keyless access is explicitly allowed/rate-limited; BSC stays unsupported
until a documented free endpoint and key are configured.
**Related rules:** OPR-009, OPR-018–019.

### OPR-009 — Secret handling and incident response
**Rule:** Never commit, log, persist, package, or publicly report credentials, secret-bearing URLs, private
data, wallet material, or an exploitable proof.
**Type:** MUST NOT. **Applies to:** Every operator and artifact.
**Trigger / Preconditions:** Handling secrets or suspected exposure.
**Required behavior:** Stop use; revoke/rotate; retain sanitized evidence; report via GitHub private
vulnerability reporting or privately request a channel; identify affected surfaces.
**Prohibited behavior:** Public issue/PR/discussion/commit disclosure or automatic history rewrite.
**Failure result:** Package generation rejects matched secrets; stored exception strings are redacted;
external rotation/remediation is required.
**Enforcement:** `storage.db.safe_error_message`, experiment `_safe`, package secret scan, tests, plus policy.
**Enforcement strength:** PARTIAL. **Source of truth:** `SECURITY.md` **Reporting/Credential exposure**.
**Evidence:** `.env`/DuckDB/Parquet/runtime outputs are ignored; package generation scans generated content.
**Exceptions / Overrides:** History purge and external remediation require an agreed, authorized plan.
**Related rules:** OPR-005, OPR-008, OPR-035, OPR-038. **Notes:** No repository-wide standalone scanner exists.

### OPR-010 — Canonical store initialization
**Rule:** Initialize and persist through the repository's single DuckDB + Parquet boundary.
**Type:** MUST. **Applies to:** Pipeline/storage operator.
**Trigger / Preconditions:** First use or opening an existing database.
**Required behavior:** Run `python -m storage <database>`; ingestion writes via `storage.db`.
**Prohibited behavior:** Alternate databases or direct writes designed to bypass canonical accessors.
**Failure result:** Schema/check/constraint failure; unsupported newer schema raises `RuntimeError`.
**Enforcement:** `storage.__main__.main`, schema DDL/checks, `storage.db.connect`. **Enforcement strength:** HARD
on canonical path.
**Source of truth:** `storage/schema.py` `SCHEMA_VERSION`/`initialize`; `storage/db.py`; `AGENTS.md` **Storage**.
**Evidence:** Repository search finds schema DDL only in `storage/schema.py`; storage initialization is idempotent.
**Exceptions / Overrides:** File-based analysis/reporting artifacts where the active contract permits them.
**Related rules:** OPR-011–013. **Notes:** No static rule prevents adding a new alternate store.

### OPR-011 — Storage migration procedure
**Rule:** A persisted table/column/key/type/partition change must update canonical schema/accessors, bump
`SCHEMA_VERSION`, migrate existing data transactionally/idempotently, and add fixture evidence.
**Type:** MUST. **Applies to:** Schema maintainer.
**Trigger / Preconditions:** Persistence contract change.
**Required behavior:** Use the storage migration skill; test fresh init, upgrade, repeat application, keys,
nullability, preservation, and rollback/error behavior.
**Prohibited behavior:** Rewriting raw ingestion meaning or creating a second store to evade review.
**Failure result:** Newer-than-code databases are blocked; migration/CI fixtures may fail.
**Enforcement:** Version ladder and dedicated CI migration test; optional unwired guard.
**Enforcement strength:** PARTIAL. **Source of truth:** `AGENTS.md` **Storage and schema boundaries**;
`.agents/skills/storage-schema-migration/SKILL.md`; `storage.schema.initialize`.
**Evidence:** CI first runs `test_v1_store_migrates_in_place_and_preserves_rows`; full tests pin current version.
**Exceptions / Overrides:** Explicitly approved migration may change the contract.
**Related rules:** OPR-010, OPR-036. **Notes:** The helper guard is not in CI. A
previous version of `docs/ARCHITECTURE.md` stated schema version 6; the current
architecture records the authoritative version 13.

### OPR-012 — Two-store verification and recovery
**Rule:** DuckDB is authoritative; verify and repair divergent OHLCV Parquet partitions rather than re-run
ingestion.
**Type:** MUST. **Applies to:** Recovery operator.
**Trigger / Preconditions:** Missing/stale/unreadable Parquet after publication/disk/permission failure.
**Required behavior:** Run `python -m storage <db> --verify-parquet`, then `--repair-parquet`; pass
`--parquet-dir` for a nondefault layout.
**Prohibited behavior:** Treating Parquet as authority or refetching to repair already committed rows.
**Failure result:** Verify emits divergent `(source,date)` records; repair rebuilds only those partitions.
**Enforcement:** Comparison, deterministic staged write/atomic replacement. **Enforcement strength:** HARD when invoked.
**Source of truth:** runbook **Verification boundaries**; `storage.db.verify_parquet_publication` and
`repair_parquet_publication`.
**Evidence:** CLI exposes independent read-only verify and mutating repair flags; repair is idempotent.
**Exceptions / Overrides:** None documented. **Related rules:** OPR-010, OPR-013.
**Notes:** Detection is manual; no scheduled drift check exists.

### OPR-013 — Persisted-state and writer safety
**Rule:** Do not delete DuckDB/Parquet while jobs run and do not run competing writer processes against one DB.
**Type:** MUST NOT. **Applies to:** Runtime operator.
**Trigger / Preconditions:** Cleanup, scheduler startup, or parallel one-pass jobs.
**Required behavior:** Stop writers before destructive local-data actions; use the single foreground scheduler.
**Prohibited behavior:** Concurrent schedulers/writers or deletion during work.
**Failure result:** Data loss or DuckDB lock/contention errors.
**Enforcement:** DuckDB process locking and per-process APScheduler overlap controls. **Enforcement strength:** PARTIAL.
**Source of truth:** runbook **Data safety**; `build_scheduler(max_instances=1, coalesce=True)`.
**Evidence:** No multiprocess writer coordinator, queue, deployment/IaC, or connection pool exists.
**Exceptions / Overrides:** None defined. **Related rules:** OPR-012, OPR-022.
**Notes:** Same-job overlap is hard-blocked only inside one scheduler process.

### OPR-014 — Network/provider boundary
**Rule:** Only `ingestion/` may contact exchanges, aggregators, explorers, RPC, or Solana services;
analysis/reporting operate on local persisted/approved artifacts without network.
**Type:** MUST NOT. **Applies to:** Developers and Phase 2–4 invocation.
**Trigger / Preconditions:** Adding I/O or running fixture acceptance paths.
**Required behavior:** Keep provider code behind ingestion adapters and run required fixture paths with
network disabled.
**Prohibited behavior:** Provider imports/calls, telemetry, or live dependencies in analysis/reporting.
**Failure result:** Socket-denial tests fail; reporting guard fails if manually invoked.
**Enforcement:** Fixture socket sabotage plus an unwired AST reporting guard. **Enforcement strength:** PARTIAL.
**Source of truth:** `AGENTS.md` **Environment/Change boundaries**; `SECURITY.md` **Security boundaries**.
**Evidence:** Current network-client imports are confined to ingestion; Phase 2–4 end-to-end tests monkeypatch sockets.
**Exceptions / Overrides:** None under current phase contracts. **Related rules:** OPR-037.
**Notes:** There is no static CI import boundary for analysis, and unexecuted network code could bypass fixtures.

### OPR-015 — Canonical identity and reconciliation
**Rule:** Use canonical, venue/chain/address-scoped identity; symbol text cannot join distinct assets.
**Type:** MUST. **Applies to:** Ingestion, normalization, analysis operators.
**Trigger / Preconditions:** Persisting, joining, or reconciling an asset.
**Required behavior:** Normalize EVM address case, preserve Solana address case, and create lineage only for
one unambiguous contract-address match.
**Prohibited behavior:** Symbol-only collapse or inferred ambiguous lineage.
**Failure result:** Ambiguous candidates remain unlinked; snapshots reject unknown/duplicate/ambiguous IDs.
**Enforcement:** Schema keys, `normalization.reconcile_assets`, `DatasetSnapshot` validation.
**Enforcement strength:** HARD on implemented paths. **Source of truth:** canonical schema and reconciliation code.
**Evidence:** `_address_key` lowercases non-Solana only; reconciliation requires exactly one candidate.
**Exceptions / Overrides:** None documented. **Related rules:** OPR-016, OPR-027.

### OPR-016 — Point-in-time and provenance integrity
**Rule:** Decisions may use only observations/effective evidence at or before decision time; retain unknowns,
deterministic ordering, exact input/config/time identities, and lineage.
**Type:** MUST. **Applies to:** Phase 2–4 data/research operators.
**Trigger / Preconditions:** Snapshot, feature, label, run, or report construction.
**Required behavior:** Use read-only snapshots, temporal joins and content identities; declare policy for any
authorized transformation.
**Prohibited behavior:** Future/late lineage leakage, cross-boundary forward fill, fabricated metadata/prices,
non-finite values, or unordered result dependence.
**Failure result:** Snapshot/temporal/leakage validator raises or value remains unavailable/censored.
**Enforcement:** `read_only=True`, snapshot duplicate/source/identity/time filters, alpha temporal validation,
deterministic hashes/tests. **Enforcement strength:** HARD on implemented flows.
**Source of truth:** `AGENTS.md` **Shared temporal and provenance invariants**; `DatasetSnapshot`.
**Evidence:** `metadata_at`, `lineage_at`, relationships/events/reference series all filter `<= decision_time`.
**Exceptions / Overrides:** Only an explicit dataset/conversion/missing policy. **Related rules:** OPR-015, OPR-028.

### OPR-017 — CEX backfill invocation and replay
**Rule:** Supply exchange, symbol, and timeframe; backfill resumes strictly after its checkpoint and is idempotent.
**Type:** MUST. **Applies to:** `python -m ingestion.cex.backfill`.
**Trigger / Preconditions:** Historical CEX ingestion.
**Required behavior:** Optionally provide ISO `--since`; otherwise configured lookback applies; use configured
DB/Parquet paths consistently.
**Prohibited behavior:** Backfilling an unsupported/nonconfigured spot market or invalid timeframe.
**Failure result:** argparse or `ValueError`; retry exhaustion propagates and run is failed.
**Enforcement:** Required CLI args, market/timeframe validation, checkpoint query, conflict-safe writes.
**Enforcement strength:** HARD. **Source of truth:** `ingestion.cex.backfill.main/backfill_symbol`.
**Evidence:** Runbook documents identical-command replay as idempotent and troubleshooting warns path mismatch
can repeat candles.
**Exceptions / Overrides:** `--config` and `--db-path` select alternate intended local configuration.
**Related rules:** OPR-010, OPR-018.

### OPR-018 — Provider capability, routing, throttle, and retry policy
**Rule:** Use configured normalized provider routes; respect auth, pagination, rate limits, timeouts, retries,
units and explicit capability states.
**Type:** MUST. **Applies to:** Ingestion operator/developer.
**Trigger / Preconditions:** Provider request or adapter change.
**Required behavior:** Retry only configured transient failures with bounded backoff/Retry-After; preserve
UNSUPPORTED, UNAVAILABLE, transient, and auth failures distinctly.
**Prohibited behavior:** Paid fallback, semantically different silent substitute, bypassed access control/rate
limit, or mapping missing risk evidence to safe.
**Failure result:** Explicit capability status, sanitized error, or raised provider error after retry budget.
**Enforcement:** Provider factories/config, capability enums, retry loops, throttlers. **Enforcement strength:** HARD.
**Source of truth:** ingestion clients/providers and `config/*.yaml`; `CONTRIBUTING.md` **Provider changes**.
**Evidence:** HTTP 429/5xx are retried; 401/403 are rejected; BSC route never falls back to Etherscan.
**Exceptions / Overrides:** Only an explicitly approved, documented provider/config change.
**Related rules:** OPR-008–009, OPR-019, OPR-038.

### OPR-019 — Missing-provider prerequisite behavior
**Rule:** A scheduler cycle skips unconfigured EVM chains and Solana, while direct provider/listener calls may
require their credential/RPC prerequisite.
**Type:** CONDITIONAL. **Applies to:** Scheduler and direct ingestion invocations.
**Trigger / Preconditions:** Missing `EVM_RPC_URL_*` or `HELIUS_API_KEY`.
**Required behavior:** Treat scheduler absence as intentional no-work; configure the exact missing value before
direct retry.
**Prohibited behavior:** Claiming the skipped path passed or substituting explorer credentials for RPC.
**Failure result:** Scheduler contributes zero rows/continues; direct RPC/client path raises.
**Enforcement:** `Pipeline.evm_listeners`, `Pipeline.solana_listener`, `JsonRpcClient`, Helius/listener behavior.
**Enforcement strength:** HARD. **Source of truth:** scheduler code plus runbook troubleshooting.
**Evidence:** README explicitly states live cycles can skip these paths and failures are recorded.
**Exceptions / Overrides:** Routescan keyless enrichment does not provide RPC observation.
**Related rules:** OPR-008, OPR-021, OPR-037. **Notes:** This scheduler/direct mismatch is intentional but operator-visible.

### OPR-020 — Durable cursor and continuation safety
**Rule:** Persist ingestion progress and advance it only after successful observation using expected-prior checks;
fail closed when a requested continuation/range cannot be proven complete.
**Type:** MUST. **Applies to:** EVM/Solana ingestion runtime.
**Trigger / Preconditions:** Restart, pagination, checkpoint or reorg-aware scan.
**Required behavior:** Resume from durable cursor/token, validate positive limits/page budgets and block ranges,
and advance monotonically/CAS-style after writes.
**Prohibited behavior:** Silently skipping an unreached continuation, regressing a cursor, or advancing incomplete work.
**Failure result:** `ValueError`/`RuntimeError`/cursor conflict; previous durable progress remains.
**Enforcement:** `advance_ingestion_cursor/continuation`; listeners' range and checkpoint guards.
**Enforcement strength:** HARD. **Source of truth:** `storage.db` cursor accessors and ingestion listeners.
**Evidence:** Solana raises when the prior signature is missing or not reached within `max_pages`; EVM validates
confirmation/reorg windows.
**Exceptions / Overrides:** None documented. **Related rules:** OPR-010, OPR-021.

### OPR-021 — One-cycle orchestration and failure recording
**Rule:** A cycle invokes CEX refresh, Tier 0, EVM, Solana, then normalization and records each job outcome.
**Type:** MUST. **Applies to:** `python -m scheduler [--once]`.
**Trigger / Preconditions:** Scheduler start.
**Required behavior:** Initialize/use the selected `--db`; log start/end, row count, sanitized error and quality
observation. `--once` prints each result and exits.
**Prohibited behavior:** Treating one provider/job failure as an unrecorded success.
**Failure result:** Job status `failed`; cycle `success` false, but subsequent jobs are still attempted.
**Enforcement:** `Pipeline.run_job/run_cycle`; per-chain EVM exception isolation. **Enforcement strength:** HARD.
**Source of truth:** scheduler modules. **Evidence:** `run_job` catches, sanitizes, persists, and returns failures.
**Exceptions / Overrides:** Missing optional EVM/Solana prerequisites produce no work rather than failure (OPR-019).
**Related rules:** OPR-022–023.

### OPR-022 — Continuous schedule and overlap control
**Rule:** Continuous mode uses UTC, one initial cycle, daily CEX, 15–30-minute Tier 0, one-minute listeners, and
02:00 normalization without overlapping the same job.
**Type:** MUST. **Applies to:** Continuous scheduler.
**Trigger / Preconditions:** `python -m scheduler` without `--once`.
**Required behavior:** Clamp configured Tier 0 interval and coalesce missed runs.
**Prohibited behavior:** Multiple concurrent instances of the same registered job in one scheduler.
**Failure result:** APScheduler coalesces/skips overlap according to `max_instances=1`.
**Enforcement:** `build_scheduler`, `BlockingScheduler`. **Enforcement strength:** HARD.
**Source of truth:** `scheduler.__main__.main`; `Pipeline.expected_job_intervals`; `build_scheduler`.
**Evidence:** Every `add_job` supplies `max_instances=1, coalesce=True`.
**Exceptions / Overrides:** Tier 0 configured values outside range are clamped, not rejected.
**Related rules:** OPR-013, OPR-021.

### OPR-023 — Monitoring and least-scope recovery
**Rule:** Check machine-readable health/data quality and retry the smallest failing boundary after correcting it.
**Type:** SHOULD. **Applies to:** Operations.
**Trigger / Preconditions:** Routine monitoring or `healthy:false`.
**Required behavior:** Run `python -m scheduler.status`; inspect latest sanitized error/config path without printing
secrets; run reconciliation report; retry isolated one-pass job; use OPR-012 for Parquet drift.
**Prohibited behavior:** Broad refetch/recovery before identifying the boundary.
**Failure result:** Failed/running historical rows make `healthy` false; no alert is emitted automatically.
**Enforcement:** Status/report CLIs calculate results; invocation is manual. **Enforcement strength:** SOFT.
**Source of truth:** runbook **Monitor/Debugging**; `scheduler.status.health_report`.
**Evidence:** Health is false if **any** stored run is failed/running, not merely the latest per job.
**Exceptions / Overrides:** None. **Related rules:** OPR-012, OPR-019, OPR-021.
**Notes:** No daemon alert/dashboard exists; old failures keep health false, which may surprise operators.

### OPR-024 — Simulator execution envelope
**Rule:** The implemented simulator supports only nonnegative-cost, long-only, single-venue CEX execution at the
next available bar open.
**Type:** MUST. **Applies to:** Phase 2 caller/config.
**Trigger / Preconditions:** `simulate`.
**Required behavior:** Select explicit `skip`/`error` missing/halted policies and
`execute_next_available`/`skip`/`error` stale policy; provide positive supported timeframe bars.
**Prohibited behavior:** Same-bar/intrabar execution, DEX/cross-venue execution, shorts, leverage, non-finite or
nonpositive prices, or negative cash/fees/slippage.
**Failure result:** `ValueError`, explicit skipped order, or insufficient-cash rejection according to policy.
**Enforcement:** `BacktestConfig.validate` and `simulate`. **Enforcement strength:** HARD.
**Source of truth:** `analysis/backtesting/simulator.py`.
**Evidence:** Pending orders require a later available open and unsupported source/venue/target quantities reject.
**Exceptions / Overrides:** Only the enumerated policies; no other execution model is approved.
**Related rules:** OPR-025–026.

### OPR-025 — Strategy/simulator separation
**Rule:** A strategy returns deterministic target-position intentions; it does not create fills or own cash,
positions, fees, slippage, or order lifecycle.
**Type:** MUST NOT. **Applies to:** Strategy authors.
**Trigger / Preconditions:** Implementing `Strategy.on_bar`.
**Required behavior:** Provide `name`, `version`, and `on_bar(BarFrame) -> TargetPosition | None` for the same asset.
**Prohibited behavior:** Direct ledger mutation, fill invention, negative target quantities, provider access.
**Failure result:** Different-asset/short intent raises; there is no ledger mutation interface exposed to strategy.
**Enforcement:** Narrow immutable protocol/frame plus simulator-owned state. **Enforcement strength:** HARD for
ledger separation; protocol shape itself is runtime/duck-typed.
**Source of truth:** `analysis/strategies/protocol.py`; simulator.
**Evidence:** All cash, positions, fees, fill prices and orders are local variables in `simulate`.
**Exceptions / Overrides:** None approved. **Related rules:** OPR-014, OPR-024.

### OPR-026 — Phase 2 metrics and artifact provenance
**Rule:** Compute metrics from the simulator equity ledger and persist deterministic run evidence with input,
policy, strategy, simulator and code identity.
**Type:** MUST. **Applies to:** Phase 2 runner.
**Trigger / Preconditions:** Completing a backtest.
**Required behavior:** Retain trades/orders/equity, fees/slippage, dataset hash/range/source filters and config hashes.
**Prohibited behavior:** Metrics from strategy internals or inferred results from ambiguous assumptions.
**Failure result:** Empty/nonfinite/non-increasing ledger raises; invalid/conflicting artifact write fails.
**Enforcement:** `analysis.metrics.core`, `analysis.runs.artifacts`, Phase 2 replay tests. **Enforcement strength:** HARD.
**Source of truth:** Phase 2 implementation and `AGENTS.md` **Metrics and manifests**.
**Evidence:** Replay tests compare normalized trades, equity, metrics, and manifest inputs.
**Exceptions / Overrides:** None documented. **Related rules:** OPR-016, OPR-024–025.

### OPR-027 — Cohort-first eligibility and exclusion evidence
**Rule:** Define new-token research cohorts from persisted events before observing winners and retain an inclusion
or exclusion decision with evidence for every observed candidate.
**Type:** MUST. **Applies to:** Phase 3 operator.
**Trigger / Preconditions:** Cohort extraction.
**Required behavior:** Declare dates, chains, event rule and quality/liquidity/coverage thresholds; call first-seen
an observation boundary, not genesis; evaluate chain quality before cohort construction.
**Prohibited behavior:** Winner-first selection or treating missing provider observations/risk as healthy/safe.
**Failure result:** Candidate/chain excluded with explicit reason such as no scope/observations, low completeness,
gap or last failure.
**Enforcement:** cohort and eligibility dataclasses/functions/tests. **Enforcement strength:** HARD on canonical flow.
**Source of truth:** Phase 3 accepted decisions; `analysis.alpha.cohort/eligibility`.
**Evidence:** Default quality policy requires >0–1 completeness and rejects absent evidence rather than defaulting.
**Exceptions / Overrides:** Versioned configured sensitivity thresholds; cohort membership remains distinct from eligibility.
**Related rules:** OPR-015–016, OPR-028.

### OPR-028 — Registered feature/label/split contracts
**Rule:** Use registered versioned feature and label definitions with declared sources, effective timestamps,
lookback, missing policy, horizons/censoring/quote treatment, and purged sealed splits.
**Type:** MUST. **Applies to:** Phase 3/6 research operator.
**Trigger / Preconditions:** Feature/label computation, comparison, or experiment-spec creation.
**Required behavior:** Resolve `(name,version)` through the registry; keep missing outcomes censored; use approved
point-in-time quote conversion; keep discovery, validation, holdout separate.
**Prohibited behavior:** Unknown/cross-version comparison without compatibility, later CEX lineage as launch
feature, silent held-out semantic changes, forward-filled label endpoints, or split leakage.
**Failure result:** `ValueError`, censored label, leakage failure, or incompatible comparison rejection.
**Enforcement:** alpha registry/labels/split validators and `ExperimentSpec.__post_init__`. **Enforcement strength:** HARD.
**Source of truth:** Phase 3 authoritative decisions and alpha implementation.
**Evidence:** Policies fix USD log-return horizons, conversion evidence and 60/20/20 split with 7-day embargo.
**Exceptions / Overrides:** Only explicitly registered compatibility/versioned conversion policy.
**Related rules:** OPR-016, OPR-027, OPR-029–030.

### OPR-029 — Candidate promotion gates
**Rule:** Candidate advancement follows the implemented staged decision machine and requires the declared baseline,
uncertainty, multiplicity, coverage, and cost evidence; holdout remains sealed until eligible.
**Type:** MUST. **Applies to:** Research operator.
**Trigger / Preconditions:** Evaluating/promoting a candidate.
**Required behavior:** Use mandatory no-trade baseline (and supported configured families), valid correction policies
and matching thresholds; record coverage/sample/missingness/censoring/cost sensitivity.
**Prohibited behavior:** Skipping stages, opening holdout early, calling low-coverage output validated alpha, or
inventing adjusted p-values absent the governing slice.
**Failure result:** Explicit rejected/nonadvanced decision; experiment runner leaves unavailable significance evidence unset.
**Enforcement:** `PromotionPolicy/evaluate_candidate_promotion`, scoring, experiment cross-validation and tests.
**Enforcement strength:** HARD. **Source of truth:** alpha evaluation and `analysis.experiments`.
**Evidence:** `BaselinePolicy` requires `no_trade`; experiment correction identities/thresholds must match promotion policy.
**Exceptions / Overrides:** Only versioned policy changes; current corrections are BH discovery and Holm confirmation.
**Related rules:** OPR-028, OPR-030–031.

### OPR-030 — Governed experiment specification and run artifacts
**Rule:** A Phase 6 experiment must be a validated declarative composition run against one local snapshot and
written as deterministic content-addressed evidence.
**Type:** MUST. **Applies to:** Experiment caller.
**Trigger / Preconditions:** Constructing `ExperimentSpec` or calling `run_experiment`.
**Required behavior:** Supply current spec version, unique registered features/horizons, supported baselines/corrections,
valid split/cost windows, code/config identity, and declarative percentile rule.
**Prohibited behavior:** Hidden executable selection behavior, unsupported features/rules, cross-partition percentile
leakage, secret-bearing output, overwriting a conflicting immutable run, or invented statistical evidence.
**Failure result:** Constructor/runner `ValueError`; missing values are excluded; conflict fails closed.
**Enforcement:** frozen dataclasses, validators, partition-local selection, safe canonical serialization and hashes.
**Enforcement strength:** HARD. **Source of truth:** `analysis/experiments/spec.py` and `runner.py`.
**Evidence:** Run ID binds spec identity, dataset identity and code version; identical input resolves identically.
**Exceptions / Overrides:** None beyond supported enumerations. **Related rules:** OPR-028–029.
**Notes:** No experiment CLI exists; this is a Python API boundary.

### OPR-031 — Research/trading claim boundary
**Rule:** Do not represent methodology/fixture passes as predictive alpha, profitability, production readiness,
investment advice, or authority for paper/live/automated execution.
**Type:** MUST NOT. **Applies to:** Researchers, operators, reporters.
**Trigger / Preconditions:** Describing results or extending scope.
**Required behavior:** Preserve `validated_alpha:false` and `live_execution:false` handoff semantics and explicit
limitations/coverage.
**Prohibited behavior:** Live/paper trading, wallet custody/signing, optimization or automated decisions without a
separately approved future design.
**Failure result:** Scope/review violation; no execution implementation exists.
**Enforcement:** Documentation and handoff flags only. **Enforcement strength:** SOFT.
**Source of truth:** `AGENTS.md` **Change boundaries**; `SECURITY.md` **Supported code**;
`analysis.alpha.handoff.phase2_strategy_spec`.
**Evidence:** Roadmap explicitly defers paper/live execution to Phases 9/10.
**Exceptions / Overrides:** A new explicitly approved design; live capital additionally requires separate authorization.
**Related rules:** OPR-029, OPR-035.

### OPR-032 — Approved Phase 4 input boundary
**Rule:** Generate only from an immutable approved local manifest whose approval is approved/reviewer-attributed and
whose Phase 3 run, artifacts, staged tables, paths and SHA-256 hashes verify.
**Type:** MUST. **Applies to:** `generate_package` caller.
**Trigger / Preconditions:** Before any rendering/package output.
**Required behavior:** Supply exact dataset/query/config/time and research lineage; use relative staged artifact paths.
**Prohibited behavior:** Mutable/unapproved/unattested/mismatched inputs, path traversal, or recomputing upstream semantics.
**Failure result:** `ValueError` before successful package generation.
**Enforcement:** `validate_approved_handoff`, staged-table hash/path validation, generator preflight.
**Enforcement strength:** HARD. **Source of truth:** `reporting/package/handoff.py`, `generate.py`, Phase 4 decisions.
**Evidence:** Cross-phase tests accept actual Phase 3 output only through an explicit approved handoff.
**Exceptions / Overrides:** None documented. **Related rules:** OPR-033–035.

### OPR-033 — Evidence-bound factual claims
**Rule:** Every factual claim, and especially every numeric/comparative claim, must resolve to staged approved evidence
with exact identities/time range/uncertainty and a typed derivation consistent with text and units.
**Type:** MUST. **Applies to:** Claim author/package generator.
**Trigger / Preconditions:** Claim-ledger validation.
**Required behavior:** Use unique nonblank IDs, fact/interpretation kinds, valid artifact row/field references, declared
operations/formatting and comparison sides. Label unsupported narrative interpretation or omit it.
**Prohibited behavior:** Unresolved facts, fabricated values, mismatched dataset/config/range/units, nonfinite inputs,
zero-denominator ratios, or prose disagreeing with derivation.
**Failure result:** `validate_claims` raises.
**Enforcement:** Typed models and derivation/prose/provenance validator invoked by generator. **Enforcement strength:** HARD.
**Source of truth:** `reporting/claims/model.py`; Phase 4 decisions.
**Evidence:** Identity/difference/ratio/percent-change operations validate row counts and derived values.
**Exceptions / Overrides:** Interpretation may be retained only when correctly typed; it cannot masquerade as fact.
**Related rules:** OPR-032, OPR-034.

### OPR-034 — Evidence-bound accessible charts
**Rule:** Chart specs must reference staged columns, declare units/source/meaningful alt text/missing behavior/readable
dimensions, and use only result-approved deterministic transforms and evidence-backed annotations.
**Type:** MUST. **Applies to:** Chart author/renderer.
**Trigger / Preconditions:** Chart validation/rendering.
**Required behavior:** Choose `explicit_state` or `fail` for missingness; validate SVG role/title/description/dimensions,
units and attribution; retain checksum/spec/renderer metadata.
**Prohibited behavior:** Fabricated zeros/interpolation/labels, unstaged data, malformed/nonfinite/empty render data,
unapproved transforms, unsupported annotations, or inaccessible SVG.
**Failure result:** `validate_chart`, renderer, or accessibility validator raises.
**Enforcement:** Chart validator, deterministic stdlib SVG renderer, structural accessibility validator.
**Enforcement strength:** HARD. **Source of truth:** `reporting/charts/spec.py`, `reporting/render/static.py`.
**Evidence:** Dimensions are constrained to 320–4096 by 180–4096; alt text has semantic/non-placeholder checks.
**Exceptions / Overrides:** Validator recognizes `identity` and `sort_x`, but a transform must exactly match manifest
approval; current implementation decision approves identity only and annotations were declared unsupported.
**Related rules:** OPR-032–033. **Notes:** The broader validator capability versus current decision is a partial mismatch.

### OPR-035 — Pending review; no publication
**Rule:** Generated Phase 4 output is a draft/review package only; a human review gate precedes any external publication.
**Type:** MUST NOT. **Applies to:** Phase 4 operator.
**Trigger / Preconditions:** Successful package generation.
**Required behavior:** Retain `review.json` with pending/approval-required state and inspect checksums, validation,
inputs, secrets and unintended paths.
**Prohibited behavior:** Generator changing review state, external publishing/distribution, automated trading, or
claiming publication approval.
**Failure result:** Repository offers no publishing transition/path; external use remains unauthorized.
**Enforcement:** Generated flags (`pending`, `approval_required`, `human_review:required`) plus absence of publication code.
**Enforcement strength:** PARTIAL. **Source of truth:** Phase 4 decisions; `reporting.package.generate`; `AGENTS.md`.
**Evidence:** Tests confirm the offline Phase 1→4 chain ends in pending review.
**Exceptions / Overrides:** Separate authorization/design outside current scope. **Related rules:** OPR-009, OPR-031–034.
**Notes:** Nothing authenticates a reviewer or technically prevents copying files externally.

### OPR-036 — Verification and truthful handoff
**Rule:** Run narrow relevant checks, then applicable repository-wide gates, and report exact outcomes without
weakening checks or claiming what did not run.
**Type:** MUST. **Applies to:** Contributor/agent.
**Trigger / Preconditions:** Any change/completion claim.
**Required behavior:** Baseline is `python -m pytest` (wrappers/locked equivalent allowed); for Python scope also use
relevant focused tests, compileall when warranted, and `git diff --check`; inspect final diff. Distinguish PASS, FAIL,
NOT RUN, BLOCKED and fixture versus live evidence.
**Prohibited behavior:** Invented CLI/checks, skipped/weakened tests, global tool installation for convenience, or false pass claims.
**Failure result:** Failed CI, or criterion reported unverified with concrete cause.
**Enforcement:** One CI job runs locked sync, storage migration test, full pytest, compileall, diff check.
**Enforcement strength:** PARTIAL because merge protection is not evidenced and local execution is manual.
**Source of truth:** `AGENTS.md` **Build/Completion**; `CONTRIBUTING.md` **Verification**; CI workflow.
**Evidence:** `scripts/run-tests` exits 2 with provisioning instructions when neither environment supplies pytest.
**Exceptions / Overrides:** Compatible `CCXT_PROJECT_VENV`; environment limitation must be reported, not bypassed.
**Related rules:** OPR-006–007, OPR-037.

### OPR-037 — Fixture evidence versus live acceptance
**Rule:** Unit/fixture/Phase 2–4 acceptance tests use deterministic mocks/local inputs with network disabled; a live
provider claim requires credentials/network and separate recorded evidence.
**Type:** MUST. **Applies to:** Test and provider-acceptance operator.
**Trigger / Preconditions:** Verification or completion report.
**Required behavior:** Run offline acceptance where required; label unavailable live evidence unverified and state the prerequisite.
**Prohibited behavior:** Live calls in unit fixtures, credentials/live commands in fixture CI, or claiming provider acceptance from mocks.
**Failure result:** Socket sabotage/CI workflow scan fails, or live criterion remains `UNVERIFIED_RUNTIME`.
**Enforcement:** Network-denial tests and `tests/test_ci.py`; reporting convention for live evidence.
**Enforcement strength:** PARTIAL. **Source of truth:** runbook **Verification boundaries**; `CONTRIBUTING.md`; tests.
**Evidence:** CI is expressly fixture-only and contains no credential/live execution step.
**Exceptions / Overrides:** Separately authorized credentialed smoke check under provider skill prerequisites.
**Related rules:** OPR-014, OPR-018, OPR-036.

### OPR-038 — Authorized security testing
**Rule:** Security testing must be authorized, proportionate, local/fixture-based, and must not affect third parties
or exfiltrate data.
**Type:** MUST NOT. **Applies to:** Security tester/operator.
**Trigger / Preconditions:** Vulnerability research or reproduction.
**Required behavior:** Use sanitized minimal fixtures; privately report concrete repository risk.
**Prohibited behavior:** Probing/abusing providers, bypassing auth/rates/paid tiers, transactions/signatures/wallet access,
credential exfiltration, live offline-test dependencies, or unsanitized proof.
**Failure result:** Stop activity and obtain external-system owner authorization; report securely.
**Enforcement:** Policy only; provider clients also throttle but are not an authorization control.
**Enforcement strength:** SOFT. **Source of truth:** `SECURITY.md` **Safe testing and research conduct**.
**Evidence:** Security policy says it grants no permission outside the repository.
**Exceptions / Overrides:** Explicit authorization from the external system owner.
**Related rules:** OPR-009, OPR-018.

## Operator Workflow

1. **Reconcile scope and state (OPR-001–006).** Read the active instruction/phase chain, roadmap frontier,
   implementation and tests. Inspect Git state; preserve unrelated work. Select only the requested coherent slice.
2. **Provision locally (OPR-007–010).** Use Python 3.10+, pinned dependencies, a private untracked `.env`, reviewed
   YAML routes, and `python -m storage storage/pipeline.duckdb`.
3. **Run ingestion intentionally (OPR-017–022).** Configure only desired providers. Run a specific backfill/one-pass
   command or `python -m scheduler --once`; continuous mode adds the overlap-controlled UTC schedule. Missing optional
   EVM/Solana prerequisites skip those scheduler paths, not prove them successful.
4. **Observe and recover (OPR-012–013, OPR-023).** Check `scheduler.status` and the reconciliation report. Correct the
   smallest failing configuration/provider boundary. For two-store drift, verify then repair from DuckDB; stop writers
   before state deletion and avoid competing writer processes.
5. **Research offline (OPR-014–016, OPR-024–031).** Materialize a read-only deterministic snapshot. Phase 2 strategies
   emit intentions for next-bar simulation. Phase 3 constructs a cohort before candidates, uses registered point-in-time
   features/labels/splits, and applies promotion evidence. Phase 6's Python API validates/content-addresses the composed run.
6. **Generate a review package (OPR-032–035).** Supply a hash-verified approved Phase 3 handoff, validate every claim and
   chart, generate deterministic Markdown/SVG and inspect the pending review package. Stop: publication is not implemented
   or authorized.
7. **Verify and hand off (OPR-009, OPR-036–038).** Run focused tests and repository gates, inspect secrets/paths/diff,
   distinguish offline fixtures from live evidence, commit only requested/coherent paths, and use a narrow reviewable PR.

## Enforcement Map

| Enforcement Surface | Rules Enforced | Mechanism | Bypass Risk |
|---|---|---|---|
| `argparse` CLI entry points | OPR-010, OPR-012, OPR-017, OPR-021, OPR-023 | Required args, enum-like flags/defaults | Python APIs can be called directly |
| DuckDB schema/migration ladder | OPR-010–011, OPR-015, OPR-020 | PK/FK/checks, transactions, schema-version rejection | Alternate direct connection/schema code is not statically forbidden |
| `storage.db` publication/recovery | OPR-009–012, OPR-020 | redaction, idempotent upserts, staging/hash comparison, cursor CAS | Verify/repair is operator-triggered |
| Provider adapters/config | OPR-008–009, OPR-018–020 | route factory, env lookup, capability enum, retry/throttle, pagination guards | Operators can call third parties outside repository code |
| Scheduler | OPR-013, OPR-019, OPR-021–023 | recorded runs, isolated exceptions, max_instances/coalescing, health JSON | Multiple scheduler processes; monitoring is manual |
| Read-only snapshot/temporal APIs | OPR-014–016, OPR-027–028 | `read_only=True`, canonical/duplicate/time validation, deterministic sort/hash | Other future analysis readers are not statically constrained |
| Simulator/metrics/artifacts | OPR-024–026 | config guards, immutable intentions, explicit ledgers, validators/hashes | Direct noncanonical research code could bypass APIs |
| Alpha/experiment governance | OPR-027–030 | eligibility reasons, registries, split/leakage/promotion/spec validation | No experiment CLI/access control; Python callers may build alternate logic |
| Reporting handoff/claim/chart/package | OPR-009, OPR-032–035 | path/hash/approval/derivation/a11y/secret/checksum validators | Approval is declarative; no authenticated reviewer/publication gate |
| Pytest fixture suite | OPR-011, OPR-014–016, OPR-024–037 | negative fixtures, replay, socket sabotage, CI-shape assertions | Tests can be edited; required branch check unknown |
| GitHub Actions `fixture-verification` | OPR-007, OPR-011, OPR-036–037 | locked sync, migration test, pytest, compileall, diff check | Branch protection is not repository-evidenced |
| Manual skill guards | OPR-011, OPR-014 | AST/storage/provider policy scripts | Not invoked by CI or hooks |
| Prose policy/review | OPR-001–006, OPR-013, OPR-023, OPR-031, OPR-035–038 | human/agent compliance | No mechanical gate |

## Conflicts and Ambiguities

1. **Schema documentation — resolved.** A previous version of `docs/ARCHITECTURE.md`
   said schema version 6, while `storage/schema.py` and tests pin 13. The current
   architecture records 13; runtime and storage code remain authoritative.
2. **Current frontier versus root phase framing — resolved for the public surface.**
   `ROADMAP.md` now records Phase 8 complete, Phase 8R active, and Phases 9–10
   deferred. Root guidance remains the repository-wide invariant source, while
   the roadmap is the forward phase authority.
3. **Python support breadth.** Metadata promises `>=3.10`; CI exercises only 3.12. Whether 3.10/3.11 remain genuinely
   supported is **UNRESOLVED**.
4. **Health semantics.** `scheduler.status` declares unhealthy if any historical run is failed/running, whereas an
   operator may expect only latest status. Code and runbook agree with current behavior, but no acknowledgement/reset
   workflow exists.
5. **Scheduler skip versus direct failure.** Missing Helius/EVM configuration quietly yields no scheduler rows, while
   direct clients/listeners reject missing prerequisites. The paths are documented but require careful evidence wording.
6. **Chart decision versus validator.** Phase 4 decisions say only `identity` is whitelisted and annotations remain
   unsupported; `validate_chart` also implements `sort_x` and evidence-backed horizontal-line annotations when approved.
   Executable behavior is broader. Whether the decision document should be updated is **UNRESOLVED**.
7. **Human approval has two meanings.** Input generation requires an `approved` reviewer field, but output is always
   pending human review. No authenticated identity or external publication control proves either review happened.
8. **CI as merge gate.** CI exists and self-tests its exact shape, but no branch-protection/ruleset-as-code establishes
   that it must pass before merge. Effective forge enforcement is **UNRESOLVED**.
9. **No license/conduct policy.** Documentation warns not to assume broad reuse or a separate conduct process. There is
   no repository evidence defining permissions beyond that warning.

## Documented-but-Unenforced Rules

The following **11** material rule groups are prose-only or lack an independent gate: OPR-001, OPR-002,
OPR-003, OPR-004, OPR-005, OPR-006, OPR-023, OPR-031, OPR-038, the external-human portion of OPR-035,
and the “do not add an alternate provider/store path” portions of OPR-010/018. Specifically:

* Phase/source precedence, one-slice discipline, roadmap status updates, Git safety, narrow PRs, no direct `main`
  push, truthful attribution, and human review rely on operators/reviewers.
* There is no branch-protection export, CODEOWNERS, required-approval count, pre-commit/pre-push hook, or authenticated
  publication approval service.
* No automation monitors health, runs the Parquet drift check, performs live-provider acceptance, measures coverage,
  runs mutation testing, or scans dependencies/licenses/SAST.
* The architectural bans on alternate stores, ingestion imports in all analysis paths, paid provider substitution,
  trading, and external publication are not repository-wide static/runtime gates.

## Enforced-but-Undocumented Rules

The following **5** materially operator-visible details arise primarily from code/tests rather than the main operator
instructions:

1. `scheduler.status` considers **any historical** failed/running run unhealthy (OPR-023).
2. Tier 0 cadence is clamped to 15–30 minutes rather than rejecting an out-of-range value (OPR-022).
3. Solana continuation must be found within the configured positive page budget, or the pass fails closed (OPR-020).
4. `ExperimentSpec` accepts only its exact spec version, supported corrections/baselines, cross-consistent horizons,
   and selection rules of the implemented percentile grammar (OPR-028–030).
5. Chart dimensions and meaningful-alt-text heuristics have exact runtime thresholds, and the validator contains
   `sort_x`/horizontal-line capabilities broader than the implementation decision text (OPR-034).

## Partial Enforcement / Alternate Paths

* `.gitignore` reduces accidental credential/runtime-data commits but does not inspect tracked content; package and
  exception redaction scan only their own output paths (OPR-008–009).
* Schema version/newer-database behavior and a migration fixture are hard, but the full migration procedure and ban on
  ad hoc DDL/alternate stores rely on review. The storage guard is manual (OPR-010–011).
* APScheduler blocks overlap only within one process; a second process can contend for DuckDB (OPR-013/022).
* Offline socket tests execute canonical fixtures, not every possible/unexecuted code path; only reporting has a static
  guard and that guard is not wired into CI (OPR-014/037).
* Canonical Phase 2–4 and experiment APIs fail closed, but Python callers can write alternate scripts that bypass those
  APIs. No service authorization boundary exists.
* Phase 4 validates declarative approval and always emits pending review, but cannot verify human identity or stop files
  being externally copied (OPR-032/035).
* CI is mechanically effective when run; repository evidence cannot show that the forge requires it for merge (OPR-036).

## Operator Failure and Recovery Paths

| Failure | Operator-visible result | Required recovery |
|---|---|---|
| Missing/invalid provider prerequisite | Scheduler skip or sanitized direct/provider failure | Configure the exact env/YAML boundary without printing values; rerun the smallest one-pass job |
| Rate limit/transient outage | Bounded retry, then failed/unavailable status | Respect retry budget/Retry-After; investigate provider and retry later, without paid fallback |
| Unsupported capability | `UNSUPPORTED` with reason/null value | Preserve state; configure only a documented supported route, never infer safety |
| Failed scheduler job | Durable failed `runs` row and `healthy:false` | Inspect status/error and config; rerun isolated job; later cycle continues independently |
| Unreached cursor/continuation or cursor conflict | Listener/storage exception; no silent advance | Preserve checkpoint, investigate pagination/reorg/concurrent writer, retry after correction |
| DuckDB/Parquet drift | Verify JSON lists missing/unreadable/mismatched partitions | Repair from DuckDB with `--repair-parquet`; rerun verify; do not re-ingest |
| Newer database schema | Immediate `RuntimeError` | Use compatible newer code or an explicitly reviewed migration; never downgrade/rewrite blindly |
| Invalid/ambiguous temporal or identity input | Snapshot/feature/label `ValueError`, unavailable/censored value | Correct canonical ID/source/timestamp/evidence; never infer or forward-fill |
| Unsupported simulator/config/order | `ValueError`, skip, or explicit rejected order per policy | Correct to supported next-bar, CEX, long-only assumptions or retain explicit outcome |
| Candidate lacks evidence | Nonpromotion/rejection | Retain stage and missing evidence; do not open holdout or claim alpha |
| Invalid handoff/claim/chart/secret | Package generation fails closed | Correct approved hashes/provenance/derivation/spec or remove/rotate secret; regenerate deterministically |
| Test/tool unavailable | Wrapper exits 2 or command cannot run | Provision locked test extra/use compatible venv; report BLOCKED/NOT RUN, never claim pass |
| Git overlap/destructive ambiguity | Operator must stop | Preserve unrelated work; report conflict and obtain explicit target/authority |
| Suspected secret/vulnerability | Public disclosure prohibited | Stop/revoke/rotate, sanitize evidence, report privately; purge history only by agreed plan |

## Coverage Gaps

* No linter, formatter gate, type checker, coverage threshold, SAST, dependency/license scanner, release/deploy pipeline,
  pre-commit hook, CODEOWNERS, branch-ruleset export, monitoring alert, or public API contract test is configured.
* `mutmut` has configuration and a work plan but is not a declared dependency or CI gate; no completed campaign may be
  inferred from its presence.
* Live provider correctness, rate-limit behavior against real services, 3.10/3.11 compatibility, multi-process operation,
  disaster recovery, authenticated approvals, and publication controls are not proven by fixture CI.
* Static boundary guards under `.agents/skills/` are optional/manual. No CI scanner prohibits future network imports in
  all analysis code or future ad hoc database writers.
* Protocol contracts for strategies/EVM providers are not statically checked. Tier 0 clients have no shared protocol.
* A supported local experiment CLI exists, but there is no deployment topology,
  external publication path, paper/live executor, license, or conduct-enforcement
  process. Insufficient repository evidence exists to assign rules to nonexistent
  interfaces.

## Summary

This map contains **38 rules**: **20 HARD**, **9 SOFT**, **9 PARTIAL**, and **0 UNKNOWN**. The rules themselves are
classified; several facts within them remain explicitly **UNRESOLVED**. Principal enforcement comes from DuckDB schema
constraints/migrations and read-only connections, provider adapters and cursor guards, scheduler state/overlap controls,
Phase 2–3 temporal/simulation/research validators, Phase 4 handoff/claim/chart/package validators, deterministic hashes,
pytest negative/replay/network-denial fixtures, and the GitHub Actions fixture job. Eleven material rule groups are
documented but not fully mechanically enforced; five material runtime constraints are not clearly exposed in primary
operator documentation. The largest gaps are unauthenticated human approval, uncertain forge protection, manually invoked
guards/monitoring/recovery, and the distinction between fixture evidence and real-provider acceptance.
