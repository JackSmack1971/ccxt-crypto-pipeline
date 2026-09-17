---
name: experiment-change-validation
description: >-
  Validates repository changes that can alter research or experiment methodology, including
  analysis/alpha, analysis/experiments, backtesting semantics, feature/label definitions,
  candidate scoring or promotion, uncertainty, split construction, and experiment/artifact
  identity. Use to map affected methodological contracts, run the narrowest sufficient focused
  checks, verify temporal/holdout and deterministic-identity boundaries, obtain an independent
  experiment_integrity_reviewer verdict, and broaden to repository gates only when evidence or
  policy justifies it. Do not use for ordinary ingestion/storage/reporting edits that cannot
  change research semantics, generic code review, or implementing the change itself.
metadata:
  version: "0.1.0"
---

# Experiment Change Validation

Validate an already-made or proposed repository change for **methodological integrity**. This workflow owns research/experiment validation, not implementation.

The governing question is: **Can this change alter what an experiment means, what evidence it may use, how candidates are compared/promoted, or the deterministic identity of the resulting evidence?**

If no, this skill should not own the task.

## 1. Reconcile authority and change surface

Read the applicable Claude Code instruction chain first: root `CLAUDE.md`, scoped `CLAUDE.md` files such as `analysis/CLAUDE.md` when present, and then any repository-declared cross-tool instructions such as root `AGENTS.md`, `analysis/AGENTS.md`, or deeper scoped policy files. Treat current code, tests, schemas/configuration, and accepted specifications as stronger evidence than stale plans.

Determine the exact candidate delta from the best available evidence: working-tree/index diff, PR diff, commit range, or an explicit file list. Do not infer untouched behavior merely from filenames when the diff shows cross-boundary effects.

Run the deterministic change classifier:

```bash
python <skill-dir>/scripts/classify_change.py --repo . --json
```

If validating a PR/commit outside the current working tree, pass paths explicitly:

```bash
python <skill-dir>/scripts/classify_change.py --path analysis/alpha/evaluation.py --path tests/test_phase3.py --json
```

Use the classifier as a **minimum contract map**, not as proof that no other contract is affected. Read [Methodology contracts](references/METHODOLOGY_CONTRACTS.md) whenever any contract family is reported.

If the change cannot affect experiment/research methodology after inspection, stop `NOT_APPLICABLE` and identify the neighboring workflow that owns it when evident.

## 2. Build the methodological impact map

For every affected contract family, identify:

- the authoritative implementation boundary;
- the invariant(s) that could be changed or bypassed;
- the focused tests or executable evidence that can falsify a bad change;
- whether identity/versioning must change when behavior changes; and
- whether failure should be explicit rejection, unavailable evidence, or another existing fail-closed state.

Mandatory contract families are listed in [Methodology contracts](references/METHODOLOGY_CONTRACTS.md). Do not mark a family `UNAFFECTED` solely because its primary file was not edited; follow calls, shared config objects, registries, serialization, and tests far enough to establish the claim.

Use these statuses only:

- `AFFECTED` — behavior or contract may change;
- `TRANSITIVELY_AFFECTED` — dependency/consumer behavior may change;
- `UNAFFECTED` — inspected evidence supports no effect;
- `INCONCLUSIVE` — available evidence is insufficient.

An `INCONCLUSIVE` consequential family prevents a final `PASS`.

## 3. Verify temporal and holdout boundaries before statistical conclusions

When feature, label, cohort, dataset snapshot, split, walk-forward, evaluation, scoring, promotion, or experiment-run behavior is affected, explicitly verify all applicable boundaries below:

1. For decision time `t`, future-observed/effective evidence cannot influence the decision.
2. Feature lookback and label horizon semantics remain declared and compatible with split/embargo construction.
3. Discovery, validation, and holdout partitions remain chronological, separated, and leakage-resistant.
4. Holdout evidence remains sealed until the implemented promotion state makes access eligible.
5. Missing, censored, ambiguous, invalid, or unsupported evidence remains explicit or fail-closed; it is never silently converted into favorable evidence.
6. Multiplicity/hypothesis-family definitions cannot be redefined after results in a way that evades the declared correction contract.

A test that merely reproduces the new implementation logic is not enough. Prefer boundary tests that would fail under look-ahead, split overlap, post-result family mutation, premature holdout use, or silent missingness coercion.

## 4. Verify semantic identity and version discipline

When any behavior contributing to a research or experiment artifact changes, establish whether the current identity mechanism actually covers that behavior.

Verify as applicable:

- identical canonical specs/configuration still produce identical IDs;
- any semantically relevant input/config/version change produces a different identity when the contract requires it;
- immutable/content-addressed artifacts reject conflicting overwrite;
- experiment specs remain declarative and free of hidden executable selection behavior;
- registered feature/label/policy identities resolve to canonical definitions;
- when executable behavior is intentionally excluded from a hash, the repository-required catalog/version bump discipline was followed;
- cross-version comparisons fail unless compatibility is explicitly declared.

Do not accept "the hash function still passes" as sufficient evidence when the change altered an unhashed behavior whose version is supposed to carry semantic identity.

## 5. Select and run the minimum sufficient focused suite

Choose checks from the **contracts affected**, not from a fixed "always run everything" list. Read [Validation matrix](references/VALIDATION_MATRIX.md) and run the smallest set that directly exercises each affected contract.

Repository-native focused anchors currently include:

```bash
python -m pytest tests/test_phase2.py
python -m pytest tests/test_phase3.py tests/test_eligibility.py
python -m pytest tests/test_phase6.py
```

Do not run all three merely because this skill activated. Run a suite only when its contract surface is affected or the change crosses a boundary it covers.

For every executed command record the command, result, and what contract it evidences. A passing focused suite proves only the contracts it actually exercises.

If a focused check fails:

- determine whether the failure is introduced by this change, pre-existing, or unresolved;
- do not broaden validation until the focused failure is understood;
- never weaken temporal/leakage, determinism, immutable-artifact, compatibility, promotion, or uncertainty gates to obtain green tests.

## 6. Independent integrity review is mandatory

After focused executable checks pass, invoke the configured Claude Code subagent **`experiment_integrity_reviewer`** using Claude Code's subagent/Task mechanism with the handoff contract in [Reviewer handoff](references/REVIEWER_HANDOFF.md).

The reviewer must be independent of the implementation reasoning and receive enough evidence to inspect the actual delta and verification results. It must not be asked to rubber-stamp a proposed conclusion.

Accept reviewer outcomes only as:

- `PASS` — no material methodological violation found and evidence is sufficient;
- `FAIL` — a concrete methodological violation is demonstrated;
- `INCONCLUSIVE` — evidence, access, or reviewer capability is insufficient.

If `experiment_integrity_reviewer` is not configured/available, report `BLOCKED` with `required independent reviewer unavailable`. Do **not** substitute self-review and do not rename another agent as equivalent without an explicit repository authority establishing equivalence.

If reviewer `FAIL`, final status is `FAIL` unless the candidate change is revised and the affected validation is rerun. If reviewer `INCONCLUSIVE`, final status is `BLOCKED`.

## 7. Decide whether broader repository gates are justified

Broaden only after focused checks and independent review are satisfactory.

Run repository-wide gates when **any** of the following is true:

- root/scoped repository policy explicitly requires them for completion;
- the change alters a shared contract consumed outside the focused test surface;
- the focused validation reveals a failure outside the expected boundary;
- imports/public APIs/configuration/serialization changed in a way that can affect unrelated packages;
- deterministic artifacts or repository-level acceptance behavior changed;
- the independent reviewer identifies a plausible cross-boundary risk that focused checks do not resolve.

When broadening is justified, use repository-configured gates rather than inventing new ones. Current root anchors include:

```bash
python -m pytest
python -m compileall -q analysis ingestion normalization reporting scheduler storage tests
git diff --check
```

A repository-wide pass does not repair a methodological failure in a focused contract.

## 8. Completion decision

Use the first applicable terminal state:

| Condition | Status |
| --- | --- |
| Change is outside this workflow after inspection | `NOT_APPLICABLE` |
| A methodological invariant is demonstrated broken | `FAIL` |
| A required focused check fails because of the candidate change | `FAIL` |
| A consequential contract remains `INCONCLUSIVE` | `BLOCKED` |
| Required focused evidence is unavailable | `BLOCKED` |
| Independent reviewer is unavailable or returns `INCONCLUSIVE` | `BLOCKED` |
| Independent reviewer returns `FAIL` | `FAIL` |
| Focused checks and reviewer pass but a justified required broader gate fails or is unavailable | `BLOCKED` unless evidence shows the candidate introduced the failure, then `FAIL` |
| Every affected contract has sufficient evidence, required checks pass, independent review passes, and any justified broader gates pass | `PASS` |

Never report predictive alpha, profitability, production readiness, or live-provider validation from offline fixture/replay evidence.

## 9. Handoff

Return a compact validation record:

**Status:** `PASS`, `FAIL`, `BLOCKED`, or `NOT_APPLICABLE`.

**Candidate:** diff/commit/PR/worktree identity actually reviewed.

**Affected methodological contracts:** each contract family with `AFFECTED`, `TRANSITIVELY_AFFECTED`, `UNAFFECTED`, or `INCONCLUSIVE`, plus one-line evidence.

**Focused verification:** commands, observed results, and the contract each command evidences.

**Temporal/holdout review:** applicable boundary checks and evidence.

**Identity/version review:** affected identities, required version changes, determinism/immutability evidence.

**Independent reviewer:** reviewer name, verdict, concrete findings, and evidence references.

**Broader-gate decision:** `RUN` or `NOT JUSTIFIED`, with reason; if run, report each result.

**Residual uncertainty/blockers:** only unresolved issues material to methodological validity.
