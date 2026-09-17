---
name: one-slice-implementation
description: >-
  Advances an existing Git repository by exactly one smallest coherent, independently
  verifiable implementation slice, verifies it, stages only attributable changes, and stops
  for review. Use only for an explicitly requested stage-only implementation pass. Do not use
  for planning, auditing, broad feature completion, refactors, commits, merges, pushes, pull
  requests, deployment, or multiple independent slices.
disable-model-invocation: true
argument-hint: "[implementation objective]"
compatibility: Requires Git and Bash-compatible shell execution in the target repository.
metadata:
  version: "1.2.0"
---

# One-Slice Implementation

Advance the repository by **exactly one smallest coherent, independently verifiable implementation slice**, then stop for review.

The user's explicit request remains authoritative. If it materially changes this workflow's defining boundary, especially by requiring multiple independent slices or commit/merge/push/deploy work, follow the user and stop applying this skill to the incompatible portion.

## 0. Preflight before any edit

The helpers live in this skill's `scripts/` directory, not the repository's. Let `<skill-dir>` be the absolute directory containing this `SKILL.md`. Invoke helpers by that absolute path with the repository as the working directory; never run `scripts/...` relative to the repository.

Run the staging-capability probe before changing repository contents:

```bash
<skill-dir>/scripts/baseline.sh --preflight
```

The command must succeed before editing. It prints the run-local evidence directory (under `${TMPDIR:-/tmp}`); copy that path verbatim into every later helper command as `<evidence-dir>`, because shell variables may not persist between commands. It also refuses in-progress merges/rebases and unresolved conflicts, and proves that both the index lock and the object store are writable without changing the index.

If the probe fails because Git metadata is not writable:

1. request the narrowest available escalation only when the active approval policy permits it;
2. rerun the preflight under that authorization, and run every later helper (`--capture`, `--extend`, staging, verification) under the same authorization; and
3. if no permitted escalation path exists or the probe still fails, stop `BLOCKED` with **zero edits**.

Do not place run-local evidence in the repository or under `.git`.

## 1. Reconcile actual repository state

Read every applicable Claude Code instruction in scope, starting with `CLAUDE.md` and deeper scoped `CLAUDE.md` files, then any repository-declared cross-tool instructions such as `AGENTS.md` / `AGENTS.override.md` and repository-defined policy or precedence rules.

Determine both:

- **intended state** from the current user objective and authoritative active specification, issue, execution plan, roadmap, ledger, or equivalent source when one exists; and
- **actual state** from implementation, tests, generated artifacts, Git state, and relevant current repository evidence.

Treat observed repository state as stronger evidence than stale planning text. Do not redo work merely because an older plan still says it is pending.

If the earliest authoritative slice is partially implemented, finish that slice before selecting downstream work, provided it can be completed without absorbing unrelated pre-existing changes.

Preserve unrelated pre-existing staged, unstaged, and untracked work exactly as found. Never reset, clean, stash, discard, rewrite, or broadly stage it.

## 2. Select exactly one eligible slice

Choose the **earliest unimplemented and unblocked dependency required to advance the authoritative active objective**.

When candidates are equally eligible, prefer, in order:

1. the smallest dependency closure;
2. the smallest blast radius; and
3. the clearest independent verification.

A slice is one cohesive behavioral, contractual, schema, infrastructure, or integration increment with an observable independently verifiable outcome. File count does not define a slice.

Its minimum necessary closure may include implementation, directly necessary tests, the smallest required supporting configuration/schema/generated artifact, and the directly attributable authoritative progress-state update.

Before editing, identify the paths the slice may need to modify, including files it may create or delete. Declaring a new path that you end up not creating is harmless. Capture the pre-edit baseline:

```bash
<skill-dir>/scripts/baseline.sh --capture <evidence-dir> -- path/to/file ...
```

If capture reports unsafe overlap, a pre-existing untracked or gitignored candidate, unsupported mixed ownership, or changed Git state that prevents reliable attribution, stop `BLOCKED` before editing.

If implementation reveals an additional required path, register it **before touching it**:

```bash
<skill-dir>/scripts/baseline.sh --extend <evidence-dir> -- path/to/new-or-clean-file ...
```

`--extend` accepts only provably untouched paths: absent and never pre-existing, or tracked with no staged or unstaged change. If it refuses a path the slice requires, stop `BLOCKED`, keeping attributable run edits unstaged.

For same-file overlap rules, read [Git attribution and safe staging](references/GIT_ATTRIBUTION.md).

## 3. Implement only the selected slice

Reuse repository-native patterns and existing abstractions when their semantics fit.

Do not add unrelated cleanup, opportunistic refactoring, style churn, dependency upgrades, architecture replacement, speculative abstraction, premature generalization, or preparation for later slices.

Do not add a dependency unless the selected slice cannot reasonably be implemented with existing capabilities and repository policy allows the addition.

Do not weaken validation, safety checks, type guarantees, tests, coverage configuration, lint rules, schema constraints, or acceptance criteria to make the slice pass.

Treat writes outside the local repository or a disposable test environment as consequential external effects. If correctness requires unauthorized deployment, production mutation, irreversible external action, a materially broader architecture decision, unrelated refactor, or downstream workstream, stop `BLOCKED` instead of expanding scope.

## 4. Verify through observed evidence

Add or update the smallest meaningful tests needed to prove the selected behavior. Prefer externally meaningful behavior, contracts, state transitions, interfaces, and failure behavior over tests that mirror implementation structure.

Run focused verification first. Then run every repository-declared check applicable to the changed scope and every broader gate required by repository policy or needed to establish non-regression.

Use check/validation modes instead of broad auto-fix modes when an auto-fix could rewrite unrelated files. Direct coverage reports, test outputs, and other verification byproducts outside the repository or into gitignored paths: staging refuses any new non-ignored untracked file outside the candidate set.

For failures:

- If the slice introduced the failure, correct it within the authorized slice and rerun the affected checks.
- If a failure may be pre-existing, establish that distinction with repository evidence when practical. Do not reset the user's tree merely to construct a baseline.
- Never call a failure a regression without evidence that this slice introduced it.
- Never dismiss a failure as pre-existing without evidence sufficient to support that claim.

Require **100% line and branch coverage of newly introduced or materially changed executable code only when the repository's existing tooling can reliably measure changed-code coverage at that granularity**. Do not alter coverage configuration, exclusions, thresholds, or test semantics to obtain the number.

If changed-code coverage cannot be measured reliably with existing repository tooling, record coverage as `UNVERIFIED`; this alone does **not** block completion because the changed-code threshold is not applicable when it is not measurable. Any repository-required coverage gate remains mandatory and must actually pass.

Missing, skipped, unavailable, or inconclusive **required** verification is never `PASS`.

## 5. Reconcile durable progress state only after verification

If the repository maintains an authoritative active plan, roadmap, checklist, ledger, generated state record, or equivalent durable progress artifact, update only the state directly attributable to the verified slice.

Do not mark later work complete, infer completion from planning text, or advance unrelated milestones.

## 6. Stage only attributable state

After required verification passes, build and stage the attributable delta:

```bash
<skill-dir>/scripts/stage_attributable.sh <evidence-dir>
<skill-dir>/scripts/verify_index.sh <evidence-dir>
```

Both commands must succeed before `COMPLETE` is available. The staging script builds the expected index in run-local storage and runs every isolation, preservation, and whitespace guard **before** its single write to the real index; any staging failure other than exit `82` leaves the real index exactly as captured. Never substitute `git add .`, `git add -A`, reset, stash, restore, or another broad/destructive shortcut.

If staging exits `86` (whitespace errors in this run's own delta), correct them within the slice, rerun the affected verification, and rerun staging; the evidence directory remains valid until staging succeeds.

If attributable changes cannot be cleanly isolated, leave this run's edits unstaged and stop `BLOCKED`.

Do not commit, amend, rebase, merge, push, create a branch, open a pull request, deploy, discard unrelated changes, or begin a second slice.

## Terminal status and working-tree disposition

Use the first applicable row. No row is optional and no `may` interpretation is allowed. Any nonzero helper exit is non-success; map it to a row with the exit-code table in [Git attribution and safe staging](references/GIT_ATTRIBUTION.md#exit-codes).

| Condition | Status | Required repository disposition |
| --- | --- | --- |
| Preflight cannot prove index writability and no permitted escalation resolves it | `BLOCKED` | **Zero edits.** Index and working tree remain as found. Evidence stays only in `$TMPDIR`. |
| Slice selection, authorization, architecture, external-effect, or attribution boundary is unresolved before editing | `BLOCKED` | **Zero edits.** Preserve all pre-existing Git state exactly. |
| Repository evidence shows no unimplemented, unblocked slice remains for the active objective | `BLOCKED` | **Zero edits.** Report `no eligible slice` with the evidence; do not invent work. |
| Required verification tool/evidence is unavailable, skipped, or inconclusive | `BLOCKED` | If discovered pre-edit: zero edits. If discovered post-edit: keep only attributable run edits **unstaged**; do not revert automatically; preserve pre-existing work. |
| A repository-required completion check is evidenced as already failing before this slice | `BLOCKED` | Do not claim success through the failing gate. If edits already exist, keep attributable run edits **unstaged** and disclose the pre-existing blocker. |
| Changed-code coverage is not reliably measurable, while every repository-required verification gate passes | `COMPLETE` candidate | Record changed-code coverage `UNVERIFIED`; continue to staging. This row does not waive any repository-required coverage gate. |
| Verification demonstrates a failure introduced by this slice and the slice cannot satisfy required checks without violating scope/policy | `FAILED` | Keep attributable run edits **unstaged** for review; do not start another slice or weaken gates. |
| Attribution/staging isolation fails after successful verification | `BLOCKED` | Leave attributable run edits **unstaged**. Preserve the pre-existing index exactly as captured. |
| Staging exits `82`, or `stage_attributable.sh` succeeds but `verify_index.sh` fails | `BLOCKED` | Stop immediately. Do not attempt cleanup, rollback, commit, or further staging; report the exact mismatch and captured evidence. |
| Exactly one slice is implemented; every required verification gate passes; applicable progress state is reconciled; staging and index verification succeed | `COMPLETE` | Only attributable review-ready changes are staged; pre-existing unrelated work remains preserved; stop for review. |

## Handoff

Return only the information needed to review this run:

**Status:** `COMPLETE`, `BLOCKED`, or `FAILED`

**Slice:** exact observable capability or contract advanced.

**Selection basis:** repository evidence establishing this as the next eligible dependency.

**Files changed:** every modified, created, deleted, or generated file attributable to this run.

**Verification:** each meaningful command/check and observed result, including test counts and changed-code line/branch coverage when measurable. Use `UNVERIFIED` only for evidence that is explicitly non-required or non-measurable under the rules above.

**Git state:** evidence directory, staging result, `verify_index.sh` result, any pre-existing related blocker, and confirmation that unrelated pre-existing work remains preserved.

**Blockers or uncertainty:** only unresolved items material to this slice.

Then halt. Do not recommend, plan, preview, or begin the next slice unless the user explicitly asks.
