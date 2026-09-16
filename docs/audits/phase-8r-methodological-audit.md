# Phase 8R Methodological Audit — Slice 8R.7

**Status:** self-review complete; independent review **BLOCKED** (reviewer unavailable in this
environment). Phase 8R does not close on this document alone — see
[Outcome](#outcome), [Candidate-state binding](#7-candidate-state-binding),
[Independent-review handoff](#8-independent-review-handoff), and [ROADMAP.md](../../ROADMAP.md).
§4's finding was corrected after this document's initial PR #66 merge — see the correction note at
the top of that section; the correction does not change §3's `PASS`/`VERIFIED` rows, only how far
the governed promotion path actually reaches.

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

> **Correction (recorded during 8R.7a scoping, see candidate state in §7):** the original text of
> this section, as merged in PR #66, understated the finding. It read the governed path as reaching
> `discovery_promoted` and stopping there. Closer inspection (prompted by attempting to spec the
> validation/holdout remediation slice) shows the governed path does not reach `discovery_promoted`
> either — it fails closed one gate earlier, at `insufficient_evidence`. The corrected finding
> below replaces the original text; nothing else in this document's §3 table is affected.

`evaluate_candidate_promotion` (`analysis/alpha/evaluation.py:191-259`) correctly implements the
full `discovery → validation → holdout` sequence and is unit-tested standalone at each stage,
including `target_stage="discovery"` with a supplied `discovery_adjusted_p_value`
(`tests/test_phase6.py:152-157`, `test_promotion_discovery_q_boundary_approves_at_or_below`) and
`target_stage="holdout"` (`tests/test_phase6.py:168-176`,
`test_promotion_holdout_alpha_boundary_confirms_at_or_below`).

However, the only place that calls it from the governed experiment path,
`run_experiment` (`analysis/experiments/runner.py:242-250`), constructs:

```python
evidence = PromotionEvidence(
    target_stage="discovery",
    effect_size=difference,
    baseline_superior=difference is not None and difference > 0,
    uncertainty_supports_effect=ci95_low is not None and ci95_low > 0,
    cost_sensitivity_passed=bool(candidate.cost_sensitivity)
    and all(value is not None and value > 0 for value in candidate.cost_sensitivity.values()),
)
decision = evaluate_candidate_promotion(candidate, evidence, spec.promotion_policy)
```

`discovery_adjusted_p_value` — a required, non-defaultable field of `PromotionEvidence` — is never
set here, so it stays `None`. `evaluate_candidate_promotion` treats a `None`
`discovery_adjusted_p_value` as `MISSING_DISCOVERY_CORRECTION` and returns
`insufficient_evidence` **before ever reaching the discovery-promoted branch**, regardless of how
strong the candidate's effect size, uncertainty, or cost sensitivity are. This is not accidental:
`tests/test_phase6.py:465-474` (`test_runner_executes_the_declared_sequence_and_honestly_withholds_significance`)
asserts exactly this outcome and documents why in its own comment: *"The runner never invents
hypothesis-family significance testing (that is Slice 6.4's job), so promotion must stay honestly
unresolved rather than a fabricated pass."*

**Implemented statistical correction machinery vs. missing governed source of significance
evidence — these are two different things, and only the second is a gap:**

- **Implemented:** `analysis/experiments/hypotheses.py` fully implements frozen-family
  identification (`freeze_hypothesis_family`) and BH/Holm correction of a *supplied* raw-p-value
  map (`evaluate_hypothesis_family`), with fail-closed behavior on missing/extra cells
  (`hypotheses.py:121-127`). This machinery is correct and already covered by
  `tests/test_phase6.py`.
- **Missing:** nothing in the governed path (`runner.py`, `control.py`, `campaign.py`) ever calls
  `evaluate_hypothesis_family`, and nothing computes or accepts a raw p-value to correct in the
  first place. `run_experiment` freezes the hypothesis family (`hypotheses.py:196`,
  `hypothesis_family.json`) purely for provenance/identity — it is never evaluated. There is
  currently **no governed, provenance-bound source of raw significance evidence anywhere in the
  codebase** that could legitimately populate `discovery_adjusted_p_value` or
  `holdout_adjusted_p_value`. `ExperimentSpec` (`analysis/experiments/spec.py`) is purely
  declarative and carries no p-value or statistical-test-identity field at all.

Consequently:

- A run produced through `execute_experiment` or `execute_campaign` today reaches only
  `insufficient_evidence` (`MISSING_DISCOVERY_CORRECTION`); it cannot currently reach
  `discovery_promoted`, `validation_confirmed`, or `holdout_confirmed`.
- The previously-identified `target_stage` hardcoding in `run_experiment` (still true — see the
  code excerpt above) is a *second*, downstream gap: even if discovery evidence were supplied,
  `target_stage` would still need to advance to `"validation"`/`"holdout"` for a campaign to reach
  `holdout_confirmed`. Fixing only the `target_stage` wiring, without also addressing the missing
  significance-evidence source, would not make a positive outcome reachable.
- `ResearchCampaign`'s promoted-hypothesis verification (`campaign.py:182-187`, requiring
  `promotion.state == "holdout_confirmed"` and a passed `validation_closure.json`) is exercised in
  the test suite only by `test_execute_campaign_rejects_unclosed_promoted_outcome`, which proves the
  *fail-closed rejection* works. There is no test — and, given the above, none is currently
  possible — that exercises a **successful** promoted campaign produced by the governed path.

This is not a correctness bug: every fail-closed gate observed behaves safely (including the
`MISSING_DISCOVERY_CORRECTION` gate itself, which is honest rather than defective), and no evidence
was found of look-ahead, silent missingness coercion, or identity weakening. It is a **completeness
gap spanning two dependent layers** — (1) no governed source of significance evidence, and (2) no
governed advancement past the discovery target stage — directly relevant to 8R.7's audit scope
("holdout integrity", "falsification completeness", "reproducibility", "positive... outcomes...
represented honestly"): the repository has never demonstrated, because it cannot yet produce, an
actual positive (promoted) research campaign through `execute_campaign`. Slice 8R.6's claim that
promoted outcomes "fail closed unless holdout confirmation and validation closure both pass" is
accurate but currently vacuous — no input can satisfy that condition through the governed runner as
written. Phase 8R's exit criterion "positive and negative outcomes are represented honestly" is met
only for negative outcomes today.

**Recommendation (not implemented in this slice, to preserve scope discipline):** see
`ROADMAP.md`'s Slice 8R.7a/8R.7b/8R.7c dependency chain, added alongside this correction. The
significance-evidence contract (8R.7a) must be decided — and, if it requires a new statistical
methodology, independently reviewed — before frozen-family correction integration (8R.7b) or
sequential governed promotion (8R.7c) can produce a legitimate `holdout_confirmed` outcome.

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
| Git commit SHA (this correction) | prepared on `main` at `cd1a1a88e24263e01302ee10c348b3d896c3f0dc` (merge of PR #67, `docs/8r7-audit-candidate-binding`); this document's §4 correction and this table are part of the next commit on top of that SHA |
| Git commit SHA (originally reviewed, PR #66) | `411cd27471625166bf0e9e90ecfe2c8928e7e322` — §3's contract table was built against this state and remains valid; only §4's characterization of how far the governed path reaches was corrected |
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
   (`cd1a1a8...`/`411cd27...` on `main`, or an explicitly newer commit you have separately verified
   and rebound). Re-run `git status`, `git log -1`, and the commands in §2 yourself before relying
   on any pass/fail claim made here.
2. **Independently verify the high-risk methodological contracts**, not just re-read this table:
   point-in-time/no-look-ahead in `analysis/alpha/evaluation.py` and `analysis/experiments/runner.py`;
   deterministic content-addressed identity and immutable-overwrite rejection in `campaign.py`,
   `research.py`, `catalog.py`; multiple-testing family-freezing in `hypotheses.py`; falsification
   completeness in `falsification.py`; negative-result handling in `campaign.py`. Treat every
   `VERIFIED`/`UNAFFECTED` row in §3 as a claim to falsify, not a fact to accept.
3. **Inspect the material campaign-promotion finding in §4 directly**, including its correction.
   Confirm for yourself, by reading `runner.py`'s `run_experiment`, `hypotheses.py`'s
   `evaluate_hypothesis_family`, and `campaign.py`'s `execute_campaign`/`verify_campaign`, that (a)
   `run_experiment` never sets `discovery_adjusted_p_value`, so every governed run currently fails
   closed at `insufficient_evidence`/`MISSING_DISCOVERY_CORRECTION`; (b) no governed, provenance-bound
   source of raw significance evidence exists anywhere in the codebase to populate that field or
   `holdout_adjusted_p_value`; (c) `target_stage` is separately hardcoded to `"discovery"` in the
   governed path even though `evaluate_candidate_promotion` at `"validation"`/`"holdout"` is
   otherwise correctly implemented and unit-tested; and (d) no positive (`holdout_confirmed`)
   campaign outcome can currently be produced end-to-end through `execute_campaign` for either
   reason. Confirm this is a completeness gap (no reachable unsafe state, and the current
   `MISSING_DISCOVERY_CORRECTION` fail-closed behavior is itself correct), not a silently-weakened
   gate. If a significance-evidence contract (`ROADMAP.md` Slice 8R.7a) has since been proposed or
   implemented, independently evaluate whether its design introduces any look-ahead, p-hacking, or
   post-hoc family redefinition risk — this is exactly the kind of methodology decision this
   review exists to catch.
4. **If the candidate state has changed** (e.g. the 8R.7a/8R.7b/8R.7c remediation slices have since
   landed), do not reuse this document's verdicts. Re-run the focused suites in §2 against the new
   SHA, re-check whether §4's corrected finding still holds, and re-bind a new §7 table before
   forming a verdict.
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
