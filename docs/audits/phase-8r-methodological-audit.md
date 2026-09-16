# Phase 8R Methodological Audit — Slice 8R.7

**Status:** self-review complete; independent review **BLOCKED** (reviewer unavailable in this
environment). Phase 8R does not close on this document alone — see
[Outcome](#outcome), [Candidate-state binding](#7-candidate-state-binding),
[Independent-review handoff](#8-independent-review-handoff), and [ROADMAP.md](../../ROADMAP.md).

This document is the executable record required by Slice 8R.7. It follows the structure of
`.agents/skills/experiment-change-validation`'s handoff contract, applied to the full Phase 8R
research-integrity surface (`analysis/experiments/`, `analysis/alpha/evaluation.py`) rather than to
a single diff, because 8R.7 audits the accumulated Phase 6–8R methodology rather than one change.

## 1. Scope and authority

Reviewed: `analysis/experiments/{campaign,catalog,closure,control,falsification,hypotheses,
negative_controls,research,runner,spec,stability,stress,uncertainty,walk_forward}.py`,
`analysis/alpha/evaluation.py` (`evaluate_candidate_promotion`), and their test coverage
(`tests/test_phase3.py`, `test_phase6.py`, `test_phase6_closure.py`, `test_phase7.py`,
`test_falsification.py`, `test_research_campaign.py`, `test_research_registry.py`,
`test_benchmark_corpus.py`, `test_phase8_closure.py`).

Authority order followed: `AGENTS.md` → `ROADMAP.md` → current code/tests/schema over stale plan
prose, per repository precedence.

## 2. Focused executable evidence

```
uv sync --locked --extra test
./.venv/Scripts/python.exe -m pytest -q                                    # 479 passed
./.venv/Scripts/python.exe -m pytest -q tests/test_phase3.py tests/test_phase6.py \
  tests/test_phase6_closure.py tests/test_phase7.py tests/test_falsification.py \
  tests/test_research_campaign.py tests/test_research_registry.py \
  tests/test_benchmark_corpus.py tests/test_phase8_closure.py                # 214 passed
```

No failures. A full-repository pass alone does not establish methodological validity; the
contract-by-contract review below is the substantive evidence.

## 3. Contract-by-contract review

| Contract | Status | Evidence |
| --- | --- | --- |
| Point-in-time / no look-ahead | UNAFFECTED (already closed) | `runner.py` composes only already-governed Phase 3 helpers (`extract_cohort`, `build_split`, `validate_temporal_alignment`); no new temporal surface introduced in Phase 8R. |
| Deterministic identity | VERIFIED | `campaign_identity`, `question_identity`/`hypothesis_identity`, `experiment_spec_id`, and run `manifest.json` all hash canonical JSON of the object minus its own id field; `research.py:225-236`, `campaign.py:117-128`, `catalog.py:59-121` reject a conflicting overwrite (`FileExistsError`) rather than silently replacing content. Confirmed by `test_campaign_artifact_is_immutable_and_replayable`, `test_campaign_identity_and_outcomes_are_deterministic`. |
| Dataset-profile binding | VERIFIED | `execute_campaign` calls `verify_dataset_profile(profile, snapshot.dataset_identity)` before running anything, and `verify_campaign` re-checks `profile["profile_identity"] == campaign.dataset_profile_identity` (`campaign.py:158-160`, `201`). |
| Multiple-testing controls | VERIFIED | `hypotheses.py` freezes the full Cartesian hypothesis family (`freeze_hypothesis_family`) and content-identifies it *before* `evaluate_hypothesis_family` accepts p-values; a supplied p-value set that doesn't exactly match the frozen family's keys is rejected (`hypotheses.py:121-127`), preventing post-hoc family narrowing. Discovery uses BH/FDR, confirmation uses Holm (`hypotheses.py:140-145`). |
| Effect-size / uncertainty | VERIFIED | `evaluate_candidate_promotion` requires a non-null, finite effect size that matches the measured baseline difference bit-for-bit (`evaluation.py:209-224`) and a positive bootstrap CI lower bound (`closure.py:66-70`); missing evidence yields `insufficient_evidence`, never a default. |
| Falsification completeness | VERIFIED | `build_falsification_evidence` evaluates every method in `policy.methods`; a method absent from the negative-control/stability evidence is reported `unavailable`/`METHOD_NOT_IMPLEMENTED`, never silently dropped, and overall `status` is `passed` only if *all* declared methods passed (`falsification.py:38-64`). This is the correct anti-cherry-picking shape. |
| Negative-result handling | VERIFIED | `execute_campaign`/`ResearchCampaign` treat `rejected_hypothesis_ids` as a first-class, equally-valid outcome; `__post_init__` only requires `rejected` and `promoted` to be disjoint and drawn from declared hypotheses, not that the campaign succeed (`campaign.py:70-76`). `test_execute_campaign_replays_a_negative_result_and_binds_all_artifacts` exercises this path end-to-end. |
| Provenance / no post-hoc rewriting | VERIFIED | Runs, registries, and campaigns are content-addressed and immutable on disk; nothing in the reviewed surface mutates a written artifact in place. |
| No execution authority implied | UNAFFECTED | Nothing in `analysis/experiments/` touches `ingestion`/execution; import boundary holds (spot-checked, no cross-boundary imports found). |
| **Promotion state machine wired through the governed runner** | **FINDING (material)** | See below. |

## 4. Finding: the governed runner cannot produce a holdout-confirmed outcome

`evaluate_candidate_promotion` (`analysis/alpha/evaluation.py:191-259`) correctly implements the
full `discovery → validation → holdout` sequence and is unit-tested standalone at each stage
(`tests/test_phase6.py:170-186` exercises `target_stage="holdout"` directly).

However, the only place that calls it from the governed experiment path,
`run_experiment` (`analysis/experiments/runner.py:242-250`), hardcodes:

```python
evidence = PromotionEvidence(
    target_stage="discovery",
    ...
)
decision = evaluate_candidate_promotion(candidate, evidence, spec.promotion_policy)
```

`target_stage` is never `"validation"` or `"holdout"` anywhere else in `analysis/experiments/`
(`control.py`'s `execute_experiment` calls `run_experiment` directly; `campaign.py`'s
`execute_campaign` calls `run_experiment` once per spec and never re-invokes evaluation at a later
stage). Consequently:

- A run produced through `execute_experiment` or `execute_campaign` can reach at most
  `discovery_promoted`; it can never reach `validation_confirmed` or `holdout_confirmed`.
- `ResearchCampaign`'s promoted-hypothesis verification (`campaign.py:182-187`, requiring
  `promotion.state == "holdout_confirmed"` and a passed `validation_closure.json`) is exercised in
  the test suite only by `test_execute_campaign_rejects_unclosed_promoted_outcome`, which proves the
  *fail-closed rejection* works. There is no test — and, given the above, none is currently
  possible — that exercises a **successful** promoted campaign produced by the governed path.

This is not a correctness bug: every fail-closed gate observed behaves safely, and no evidence was
found of look-ahead, silent missingness coercion, or identity weakening. It is a **completeness
gap** directly relevant to 8R.7's audit scope ("holdout integrity", "falsification completeness",
"reproducibility", "positive... outcomes... represented honestly"): the repository has never
demonstrated, because it cannot yet produce, an actual positive (promoted) research campaign
through `execute_campaign`. Slice 8R.6's claim that promoted outcomes "fail closed unless holdout
confirmation and validation closure both pass" is accurate but currently vacuous — no input can
satisfy that condition through the governed runner as written. Phase 8R's exit criterion "positive
and negative outcomes are represented honestly" is met only for negative outcomes today.

**Recommendation (not implemented in this slice, to preserve scope discipline):** a follow-up
slice should extend the governed runner/control boundary to drive a candidate through validation
and sealed-holdout evaluation (reusing `evaluate_candidate_promotion`'s existing `target_stage`
contract) so that a legitimate `holdout_confirmed` outcome is actually reachable and testable
end-to-end, before any positive campaign result is treated as evidence-backed.

## 5. Independent reviewer

The skill `.agents/skills/experiment-change-validation` and `ROADMAP.md`'s Slice 8R.7 text both
require an independent Codex `experiment_integrity_reviewer` verdict; `REVIEWER_HANDOFF.md` states
explicitly: *"Self-review is not independent verification... If the named reviewer is not
configured or cannot be invoked, the parent workflow returns `BLOCKED`."*

This session checked for a reachable `experiment_integrity_reviewer` agent (`ListAgents`) and found
none configured in this Claude Code environment. No other subagent was substituted, and no verdict
was fabricated.

**Independent reviewer verdict: BLOCKED — required independent reviewer unavailable.**

## 6. Outcome

Per the completion table in `.agents/skills/experiment-change-validation/SKILL.md` §8: *"Independent
reviewer is unavailable or returns `INCONCLUSIVE`" → `BLOCKED`.*

**Slice 8R.7 status: BLOCKED.** The self-review portion above is complete, found no demonstrated
methodological-integrity violation, and surfaced one material completeness gap (§4). Phase 8R
cannot be marked complete from this document alone: closure requires either (a) configuring and
running the named independent reviewer against this evidence, or (b) an explicit, documented
repository-authority decision to accept an alternative review path. Neither has happened as of this
audit.

This audit itself does not authorize any execution-phase activation.

## 7. Candidate-state binding

This audit binds to the exact repository state below. An independent reviewer MUST re-verify
against this state (or an explicitly re-bound successor state) rather than trust the values in this
document.

| Field | Value |
| --- | --- |
| Git commit SHA (reviewed) | `411cd27471625166bf0e9e90ecfe2c8928e7e322` (merge of PR #66, `docs/phase-8r-methodological-audit`) |
| Branch | `main` |
| Working tree | Clean at the reviewed SHA except one untracked, repository-unrelated file (`CLAUDE.md`, a Claude Code project-instructions file with no effect on `analysis/experiments`, `analysis/alpha`, or any pipeline contract) |
| Local vs. `origin/main` | Identical (`git reset --hard origin/main` performed as part of this follow-up; no local-only commits remain) |
| Methodology/schema versions in scope | `CAMPAIGN_VERSION = "phase8r-research-campaign-v1"` (`campaign.py`); `MANIFEST_VERSION = "phase8r-run-v1"` (`runner.py`); `PromotionPolicy.version = "candidate-promotion-v1"` (`evaluation.py`); storage `SCHEMA_VERSION` unaffected by this audit's scope |
| Research campaign ID | **None** — no `campaign.json` artifact exists anywhere in the repository tree at this commit. `execute_campaign(...)` writes to a caller-supplied `campaign_root` (see `README.md`'s `write-campaign`/`execute_campaign` usage); no default in-repo output directory is defined, and per `AGENTS.md`/this repo's ephemeral-artifact convention such run/campaign output is expected to stay untracked and local. This audit's §4 finding is therefore established by static/code review and by the unit-level evidence in `tests/test_phase6.py` and `tests/test_research_campaign.py`, not by inspecting a concrete persisted campaign. |
| Dataset-profile identity/hash | **None bound** — no `profile.json` is checked into the repository; profiles are content-addressed per `analysis/datasets/profile.py`'s `write_dataset_profile` but, like campaigns, are written to a caller-chosen local directory and are not repository artifacts. |
| Campaign/run manifest hashes | **None available** — no `manifest.json` exists in-tree to hash (see above). If a specific reviewer run does produce one, bind it here (`sha256` of `manifest.json`, per `campaign.py`'s own `artifact_identities["run:<run_id>:manifest"]` convention) rather than inventing a separate hash scheme. |
| Experiment/hypothesis registry identity | **None bound** — `ResearchRegistry.identity()` is likewise computed from a registry only at construction/write time; no registry JSON is checked into the repository at this commit. |
| Verification results | See §2 (repository-wide and focused suite, both PASS at this SHA) and §8 below. |

If a future reviewer (or this repository) produces a concrete campaign/profile/registry artifact
for review, bind its identities into a copy of this table rather than editing this one in place —
this document's own identity should remain replayable to exactly the state in the row above.

## 8. Independent-review handoff

This section is the exact instruction set for the independent reviewer required to close Slice
8R.7. It supersedes no part of `.agents/skills/experiment-change-validation`; where that skill's
`experiment_integrity_reviewer` contract applies, the reviewer should be invoked through that
existing contract rather than through a new or parallel review procedure defined here.

**Reviewer instructions:**

1. **Bind to state, don't trust this document's claims.** Start from the candidate state in §7
   (`411cd27...` on `main`, or an explicitly newer commit you have separately verified and rebound).
   Re-run `git status`, `git log -1`, and the commands in §2 yourself before relying on any
   pass/fail claim made here.
2. **Independently verify the high-risk methodological contracts**, not just re-read this table:
   point-in-time/no-look-ahead in `analysis/alpha/evaluation.py` and `analysis/experiments/runner.py`;
   deterministic content-addressed identity and immutable-overwrite rejection in `campaign.py`,
   `research.py`, `catalog.py`; multiple-testing family-freezing in `hypotheses.py`; falsification
   completeness in `falsification.py`; negative-result handling in `campaign.py`. Treat every
   `VERIFIED`/`UNAFFECTED` row in §3 as a claim to falsify, not a fact to accept.
3. **Inspect the material campaign-promotion finding in §4 directly.** Confirm for yourself, by
   reading `runner.py`'s `run_experiment` and `campaign.py`'s `execute_campaign`/`verify_campaign`,
   that (a) `target_stage` is hardcoded to `"discovery"` in the governed path, (b)
   `evaluate_candidate_promotion` at `"validation"`/`"holdout"` is otherwise correctly implemented
   and unit-tested, and (c) no positive (`holdout_confirmed`) campaign outcome can currently be
   produced end-to-end through `execute_campaign`. Confirm this is a completeness gap (no reachable
   unsafe state), not a silently-weakened gate.
4. **If the candidate state has changed** (e.g. a remediation slice implementing validation/holdout
   promotion has since landed), do not reuse this document's verdicts. Re-run the focused suites in
   §2 against the new SHA, re-check whether §4's finding still holds, and re-bind a new §7 table
   before forming a verdict.
5. **Classify findings by severity** (e.g. blocking / material / advisory) rather than a single
   pass/fail label, so a partial remediation can be tracked precisely.
6. **Return exactly one of `PASS`, `FAIL`, or `INCONCLUSIVE`**, consistent with
   `.agents/skills/experiment-change-validation/SKILL.md` §6's accepted outcomes. Do not return a
   novel status.
7. **State explicitly whether Phase 8R may close.** Per `ROADMAP.md`'s Phase 8R exit criteria,
   closure requires both a `PASS` independent verdict *and* resolution (or an explicit,
   documented repository-authority acceptance) of §4's material finding. A `PASS` verdict on
   methodological soundness alone does not, by itself, close Phase 8R while §4 remains open.
8. **Bind the verdict to the exact state reviewed.** Record the Git SHA (and, if applicable,
   campaign/run/profile/registry identities) the verdict applies to, using the same fields as §7,
   so the verdict cannot be silently carried forward to a different, unreviewed candidate state.
