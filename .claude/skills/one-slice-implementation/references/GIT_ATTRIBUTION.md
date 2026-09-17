# Git Attribution and Safe Staging

Read this reference when a candidate path already contains staged or unstaged tracked changes, when ownership is mixed, or when any helper exits nonzero.

## Invariant

Reason about Git as three distinct layers:

1. `HEAD` — committed baseline;
2. index — already staged state; and
3. working tree — unstaged and untracked state.

Preserve the user's pre-existing state in all three layers. Attribution must come from captured repository evidence, not memory, timestamps, intent, or `git diff HEAD` alone.

Never use reset, restore/checkout of user content, clean, stash, amend, rebase, broad staging, or a formatter/generator that rewrites overlapping user work merely to simplify attribution.

## Normative scripted procedure

The skill ships three Bash helpers plus a sourced `lib_common.sh`. Invoke them as `<skill-dir>/scripts/...` with the repository as the working directory. Run-local evidence always lives under `${TMPDIR:-/tmp}`. All helpers pin Git configuration that could change patch bytes, context matching, or path quoting (`color.ui`, `diff.noprefix`, `diff.mnemonicPrefix`, `core.quotepath`, `apply.whitespace`, `apply.ignoreWhitespace`, external diff drivers) and target bash 3.2+.

### 1. Prove staging is possible before edits

```bash
<skill-dir>/scripts/baseline.sh --preflight
```

The probe refuses in-progress merge/rebase/cherry-pick/revert/bisect/sequencer state and any unresolved conflict entry anywhere in the index, resolves the active index path, refuses to interfere with an existing `index.lock`, creates and removes that exact lock path, and creates and removes a probe file in the object store (which linked worktrees share and which staging must write). It leaves the index bytes unchanged and prints the evidence directory. Failure means `BLOCKED` before editing unless a permitted escalation can make the same probe pass.

### 2. Capture the selected paths immediately before edits

```bash
<skill-dir>/scripts/baseline.sh --capture <evidence-dir> -- path/to/file ...
```

Capture records:

- `HEAD`, branch identity, the exact index file, and its tree;
- staged/unstaged/untracked status evidence;
- hashes of pre-existing changed and untracked paths that must be preserved; and
- lossless pre-edit working-tree snapshots of candidate regular files.

Duplicate paths are recorded once. A declared path that is never created is skipped at staging. A gitignored untracked candidate stops capture (exit `81`). A pre-existing untracked candidate is mixed ownership for its first Git snapshot. If this run would need to modify and stage it, capture stops `BLOCKED` unless the user explicitly authorizes including the pre-existing content.

Capture also blocks overlapping states whose semantics cannot be isolated safely, including unresolved conflicts, an in-progress merge/rebase/cherry-pick/revert unrelated to the slice, pre-existing deleted candidate files, and non-text overlap that requires partial attribution.

### 2a. Register a newly discovered path

```bash
<skill-dir>/scripts/baseline.sh --extend <evidence-dir> -- path/to/file ...
```

Run this before touching the path. It accepts only paths that are absent and were never recorded as pre-existing work, or tracked paths with no staged or unstaged change. Any edit made before extension, and any user-owned work, falsifies both conditions, so extension cannot absorb user content. It is refused after staging and if the real index changed since capture.

### 3. Stage the attributable delta

```bash
<skill-dir>/scripts/stage_attributable.sh <evidence-dir>
```

For candidate paths with no pre-existing unstaged change, the helper constructs the expected index from the captured index plus the final candidate state.

For a tracked regular file with pre-existing unstaged content, the helper passes the captured pre-edit working file and the final working file through the path's clean filters (end-of-line conversion, LFS, and similar), so the delta is expressed in index representation rather than checkout bytes. It derives that delta with three lines of context (`-U3`) using fixed temporary file names, so the real path is never parsed from patch headers, and applies it strictly (no fuzz, no whitespace leniency) to a detached copy of the captured index blob. If the context no longer matches because the agent edit is too close to a pre-existing user hunk, isolation fails (exit `79`). A change of executable bit on an overlapping path also fails isolation.

After every candidate is represented in the temporary index, and **before** the only real-index write, the helper:

1. derives the reviewable `attributable.patch` (captured index tree → expected index tree);
2. proves every pre-existing unrelated path is still byte/type identical and that no new unrelated unstaged or untracked path exists (exit `84`/`85`);
3. runs a whitespace check on this run's delta only (exit `86`; fix and restage);
4. confirms the real index still equals the captured index tree; and
5. writes the exact expected entries (mode and blob ID) with one `git update-index --index-info`, then confirms the real index tree equals the expected tree.

Because the final write copies object IDs instead of re-applying a patch, repository apply or whitespace configuration cannot alter staged content.

Do not force isolation with `--3way`, `--reject`, whitespace fixing, hand-authored replacement content, or reduced context merely to make it apply. A context reduction such as `-U1` changes the attribution risk model and must be treated as an evaluated design change, not an ad-hoc recovery step.

### 4. Verify the resulting index

```bash
<skill-dir>/scripts/verify_index.sh <evidence-dir>
```

The verifier mechanically checks that:

- current `HEAD` and branch identity match the capture;
- the real index tree exactly equals the expected index tree;
- therefore pre-existing staged state is preserved and no extra staged state was introduced;
- pre-existing unrelated changed and untracked paths still have the captured type/content hash;
- no new unrelated unstaged or untracked path appeared outside the candidate set; and
- this run's delta passes `git diff --check` (pre-existing staged work is never whitespace-checked).

These checks prove several Git-state invariants, but they do not prove semantic facts such as whether an attributable edit was an accidental formatter rewrite or whether the handoff fully disclosed a related dependency. Those remain reviewable workflow assertions.

## Manual interpretation of overlap

The scripts deliberately prefer false blocking to accidental capture of user work.

Safe same-file overlap requires all of the following:

- the candidate was tracked before the run;
- the pre-existing working-tree version was captured losslessly;
- this run's final delta can be expressed as a patch from that captured version;
- that patch applies cleanly to the captured index without depending on the user's unstaged hunk; and
- the final expected index can be reproduced exactly and verified after staging.

Stop `BLOCKED` before editing when the required slice would need to rewrite, regenerate, rename, normalize, structurally transform, or otherwise absorb the same region containing pre-existing user work.

If a previously safe edit becomes coupled to user-owned content during implementation, do not broaden the attribution assumption. Stop according to the terminal-status table in `SKILL.md`.

## Exit codes

| Code | Meaning | Disposition |
| --- | --- | --- |
| `64`–`66` | Invalid invocation, unsupported path characters, or evidence misuse | Correct the invocation if the cause is yours; otherwise `BLOCKED`. |
| `69`, `73`, `76` | Not a repository / no HEAD, cannot create evidence, operation or conflict in progress | `BLOCKED`, zero edits. |
| `75` | `index.lock` already exists | Wait briefly and retry once; if it persists, `BLOCKED`, zero edits. |
| `77` | Index or object store not writable | Apply the escalation rule in `SKILL.md` step 0; otherwise `BLOCKED`, zero edits. |
| `78`, `81` | Untracked, gitignored, or extension-ineligible candidate | From capture: `BLOCKED`, zero edits. From `--extend`: do not touch that path; `BLOCKED` with edits unstaged if the slice needs it. |
| `70`, `74`, `79`, `80`, `84`, `85`, `90` from staging | Isolation, concurrency, preservation, or internal failure | `BLOCKED`; edits stay unstaged; real index is exactly as captured. |
| `86` from staging | Whitespace errors in this run's delta | Fix within the slice, rerun affected verification, rerun staging. |
| `82`, or any `verify_index.sh` failure | Integrity mismatch after the real-index write | Integrity-mismatch row: stop, no cleanup or rollback, report evidence. |
