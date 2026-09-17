# Independent Reviewer Handoff

The validation workflow requires an independent Claude Code subagent named `experiment_integrity_reviewer`. Invoke that existing subagent through Claude Code's subagent/Task mechanism; this skill does not define or replace the agent.

## Required reviewer input

Provide the reviewer:

1. candidate identity: worktree diff, PR, or commit/range;
2. exact changed paths and relevant diff excerpts/full diff access;
3. the methodological impact map;
4. applicable authoritative repository instructions/contracts;
5. focused commands and observed results;
6. temporal/holdout analysis;
7. identity/version analysis;
8. any known pre-existing failures or unavailable evidence.

Do not provide a requested verdict or suggest that the change "should pass."

## Reviewer remit

The reviewer should independently attempt to falsify methodological integrity, emphasizing:

- look-ahead / temporal leakage;
- discovery-validation-holdout contamination or premature holdout access;
- feature/label horizon and split geometry;
- post-result hypothesis-family or correction-policy manipulation;
- silent missingness/censoring/uncertainty coercion;
- stale semantic versions or identities after behavior change;
- non-deterministic or under-specified experiment/run/artifact identity;
- mutable/conflicting content-addressed artifacts;
- hidden executable selection/scoring behavior outside declarative specs/registries;
- unintended changes to backtest execution/accounting semantics;
- live-network/provider access introduced into offline analysis;
- evidence that tests only mirror implementation and would not catch the relevant methodological defect.

## Output contract

Require exactly one top-level verdict: `PASS`, `FAIL`, or `INCONCLUSIVE`.

The reviewer must then provide:

- findings ordered by severity;
- repository paths/symbols or diff evidence for each finding;
- which methodological contract is affected;
- whether the finding is demonstrated or a remaining uncertainty;
- what additional evidence would resolve an `INCONCLUSIVE` item.

A `PASS` requires enough inspected evidence to support it; absence of a discovered problem alone is not sufficient.

## Missing reviewer

If the named reviewer is not configured or cannot be invoked, the parent workflow returns `BLOCKED`. Self-review is not independent verification.
