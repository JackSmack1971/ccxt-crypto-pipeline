# Version Control

| | |
|---|---|
| **Status** | Active |
| **Applies to** | Repositories that adopt this policy |
| **Owner** | Repository maintainers |
| **Last reviewed** | 2026-09-11 |
| **Review cadence** | Every 6 months, or after a VCS-related incident |

This document defines default version-control policy for both human contributors and coding
agents, including OpenAI Codex CLI.

"MUST", "MUST NOT", "SHOULD", and "MAY" use their RFC 2119 meanings.

Repository-local instructions, including applicable `AGENTS.md`, `AGENTS.override.md`,
contributor documentation, CI configuration, and explicit operator instructions, take
precedence when they are more specific. Existing forge rules and branch protections remain
authoritative for remote operations.

The intent is to preserve safety, traceability, and reviewability **without making routine
agent work depend on network access, credentials, signing keys, globally installed tools,
interactive Git commands, or human approval when those are not inherently required**.

If a rule cannot be satisfied in the current environment, do not silently bypass a safety
boundary. Complete all safe local work that remains possible, report the unmet gate clearly,
and leave the repository in a reviewable state.

---

## 0. Codex execution profile

These rules are designed to keep Codex CLI productive across local, sandboxed, CI, worktree,
and partially connected environments.

### 0.1 Local-first operation

Codex SHOULD assume that local repository operations are available and that remote operations
may not be.

Unless the task or repository instructions explicitly require otherwise, Codex MUST NOT make
successful completion of local implementation depend on:

- `git fetch`, `git pull`, `git push`, or remote ref discovery;
- GitHub/GitLab API access;
- `gh`, `glab`, or another forge CLI;
- creating a pull request;
- changing branch-protection or repository settings;
- obtaining a human approval;
- commit or tag signing;
- installing global Git configuration;
- installing system-wide hooks, scanners, or credentials.

Remote actions are a separate execution boundary. Perform them when the task explicitly asks
for them and the environment is already authorized to do so.

### 0.2 Respect the current Git state

Before editing, inspect enough repository state to avoid overwriting unrelated work:

```bash
git status --short
git branch --show-current
git diff --stat
git diff --cached --stat
```

Codex MUST preserve unrelated pre-existing working-tree and index changes.

A dirty worktree is **not** itself a blocker. Continue when the requested change can be made
without overwriting or ambiguously absorbing unrelated work. If changes overlap materially,
avoid destructive cleanup and report the overlap.

Codex MUST NOT use `git reset --hard`, `git clean -fd`, checkout-based discard commands,
history rewriting, or force pushes merely to obtain a clean starting state.

### 0.3 Branches are workflow-dependent

Codex MUST NOT create, rename, switch, delete, or rebase branches solely to satisfy a generic
policy.

Use the branch already selected by the operator unless:

- the task explicitly asks for branch creation or branch management;
- repository-local instructions require a task branch; or
- a remote workflow being performed requires one.

`main` remains the canonical integration branch, but local work is not invalid merely because
Codex is currently on `main`.

### 0.4 Commits are task-dependent

Codex MUST NOT create a commit merely because files were modified.

Commit when:

- the operator asks for a commit;
- repository-local instructions make a commit part of the requested workflow; or
- the active execution harness requires committed output.

If the task asks Codex to stop with staged or unstaged changes, do exactly that.

Codex MUST NOT amend or rewrite pre-existing commits unless explicitly authorized.

### 0.5 Use repository-local verification

Prefer the repository's own documented and pinned commands.

Codex SHOULD discover validation from sources such as:

- `AGENTS.md` / `AGENTS.override.md`;
- `README`, `CONTRIBUTING`, or development docs;
- package scripts;
- `Makefile`, `justfile`, `Taskfile`, or equivalent;
- CI workflow definitions;
- repository-local skills or scripts.

Do not invent a universal test command when the repository already defines one.

If a required tool is unavailable, report the affected check as `NOT RUN` or `BLOCKED` rather
than silently installing global software or pretending the gate passed.

### 0.6 Avoid interactive Git operations by default

Prefer non-interactive, reproducible commands. Do not use interactive rebases, editors, or
prompts during routine agent execution unless the task specifically requires them and the
environment supports them.

### 0.7 Preserve truthful evidence

Never report a check, review, commit, push, merge, or release as successful unless it actually
completed.

When handing work back, distinguish at minimum:

- **PASS** — command or check completed successfully;
- **FAIL** — command ran and failed;
- **NOT RUN** — intentionally not executed;
- **BLOCKED** — could not execute because of an environmental or policy dependency.

---

## Quick reference

The rules that cover most daily work:

1. **Preserve existing work.** Do not discard, absorb, or rewrite unrelated changes.
2. **Keep each change coherent and reviewable.** Prefer the smallest independently verifiable
   implementation slice that satisfies the task.
3. **Use repository-defined validation.** Do not require globally installed tooling when the
   repository does not.
4. **Do not rewrite shared history.** Existing commits and protected refs are immutable unless
   an explicit recovery task says otherwise.
5. **Treat remote actions as separate.** Local implementation must not require network access,
   forge credentials, PR creation, or merge permissions unless the task does.
6. **Never commit secrets.**
7. **Report verification truthfully.** Missing infrastructure is a reported limitation, not a
   reason to fabricate success.

A typical local Codex loop is intentionally simple:

```bash
git status --short
# inspect applicable instructions and relevant code
# make the requested change
# run repository-defined focused verification
git diff --check
git status --short
```

Stage, commit, push, open a PR, or merge only when the active task calls for those actions.

---

## 1. Repository model

### 1.1 Canonical integration branch

`main` is the default canonical integration branch unless the repository documents another
branch.

- `main` SHOULD remain releasable.
- Incomplete work that lands on `main` SHOULD be unreachable by users or otherwise safe by
  construction.
- Long-lived divergence SHOULD be avoided.
- Small, independently verifiable changes are preferred to large speculative branches.

This policy does not require Codex to create a feature branch for every task. Branch lifecycle
is a collaboration and deployment concern, not a prerequisite for local implementation.

### 1.2 Task branches

When the repository or operator requires a branch, use a short-lived branch appropriate to the
change.

Recommended prefixes:

| Prefix | Purpose |
|---|---|
| `feat/` | New user-facing capability |
| `fix/` | Bug fix |
| `chore/` | Tooling, dependencies, CI, non-behavioral work |
| `docs/` | Documentation only |
| `refactor/` | Behavior-preserving restructuring |
| `hotfix/` | Urgent production fix |
| `release/` | Maintenance of an explicitly supported release line |

These are defaults, not grounds for renaming an already active branch.

### 1.3 Incomplete work

Incomplete work on an integration branch SHOULD be safe and unreachable by normal users.
Common mechanisms include:

1. **Feature flag** — code path exists but defaults off.
2. **Not wired up** — module exists but nothing invokes it.
3. **Branch by abstraction** — new implementation is hidden behind an existing boundary.

Avoid dead-code toggles such as `if (false)` as a substitute for a real rollout mechanism.

---

## 2. Branch naming

When creating a new branch, prefer:

```text
<type>/<issue-id>-<kebab-case-summary>
```

or, when no issue exists:

```text
<type>/<kebab-case-summary>
```

Examples:

```text
feat/1234-oauth-device-flow
fix/1287-null-deref-on-empty-cart
chore/deps-bump-pytest-8
docs/update-installation-guide
```

Rules:

- Use a repository-approved type or one from §1.2.
- Include an issue ID when one exists and is relevant.
- Keep the summary short, lowercase, and hyphen-separated.
- Do not put secrets, customer-sensitive data, credentials, or incident-sensitive details in
  branch names.

Do not rename an existing branch simply because its name does not match this convention unless
the operator asks for cleanup.

---

## 3. Commits

### 3.1 What belongs in a commit

A commit is a durable review and revert boundary.

When committing:

- Each commit SHOULD represent one coherent logical change.
- The committed state SHOULD build and pass the checks appropriate to that change.
- Avoid mixing unrelated drive-by changes.
- Pure formatting, file movement, or generated changes MAY be separated when doing so
  materially improves reviewability, but separate commits are not mandatory when they would
  create artificial fragmentation.
- Prefer explicit staging of intended paths when unrelated changes already exist.

Do not use commit creation as a substitute for verification.

### 3.2 Commit message format

Use the repository's configured commit-message convention.

If the repository does not define one, prefer Conventional Commits 1.0.0:

```text
<type>(<scope>)<!>: <subject>

<body>

<footer>
```

Common types:

| Type | Meaning |
|---|---|
| `feat` | New capability |
| `fix` | Bug fix |
| `perf` | Performance improvement |
| `refactor` | Behavior-preserving restructuring |
| `docs` | Documentation only |
| `test` | Tests only |
| `build` | Build system or dependency change |
| `ci` | CI configuration |
| `chore` | Maintenance |
| `revert` | Revert of a prior change |

Guidance:

- Use an imperative, concise subject.
- Describe the behavior or intent, not just the filename.
- Add a body when the reason or tradeoff is not obvious from the diff.
- Reference issues when useful.
- Use `BREAKING CHANGE:` only for an actual compatibility break.

### 3.3 Attribution

Do not invent authors, email addresses, issue IDs, or co-author trailers.

Codex MUST NOT add an AI `Co-authored-by:` trailer unless repository policy or the operator
explicitly requires it and the exact attribution identity is known.

Git author configuration belongs to the execution environment. Codex should use the existing
repository/machine identity rather than rewriting global identity settings.

### 3.4 What never goes in a commit

- Secrets or credentials.
- Unrequested build outputs or generated artifacts that the repository intentionally ignores.
- Editor or OS cruft.
- Unrelated changes accidentally swept into the task.
- Large binaries that violate the repository's existing storage policy.

Lockfiles, generated sources, fixtures, snapshots, and binaries MAY be committed when the
repository intentionally tracks them.

---

## 4. History hygiene

### 4.1 Shared history is immutable by default

Do not rewrite commits another actor may depend on.

| State | Rewrite default |
|---|---|
| Uncommitted local work | Modify as needed, preserving unrelated work |
| New commits created by the current task and not shared | Only if the task permits |
| Pre-existing local commits | Do not rewrite |
| Pushed/shared feature branch | Do not rewrite unless explicitly authorized |
| `main`, release branches, or pushed tags | Never rewrite during normal work |

Codex MUST NOT run an interactive rebase, amend an existing commit, or force-push as routine
cleanup.

### 4.2 Integrating upstream changes

Fetching, pulling, rebasing, and pushing are remote operations. Perform them only when the task
requires synchronization and remote access is available.

When synchronization is requested:

1. inspect the current branch and worktree;
2. fetch without discarding local work;
3. follow the repository's documented integration strategy;
4. stop rather than guessing through a destructive or ambiguous conflict.

Do not change global `pull.rebase`, `rerere`, `rebase.updateRefs`, or similar settings as part
of a repository task.

### 4.3 Force-pushing

Force-pushing is exceptional.

If a task explicitly authorizes rewriting an unprotected task branch, prefer:

```bash
git push --force-with-lease
```

Never use plain `--force` as a convenience.

Codex MUST NOT force-push protected integration or release refs.

### 4.4 Cleanup before review

A readable history is useful, but history polishing is secondary to preserving evidence and
avoiding unintended rewrites.

Do not autosquash, amend, or rebase solely to make history aesthetically perfect unless the
operator or repository workflow asks for it.

Squash merge can provide a clean integration history without requiring local history surgery.

---

## 5. Pull requests

### 5.1 PR creation is not a local prerequisite

Codex MAY create or update a PR when:

- the task explicitly requests it;
- forge credentials are already available; and
- doing so does not require bypassing a security boundary.

If PR creation is not requested or cannot be performed, complete the local work and provide a
PR-ready summary instead. Do not treat lack of `gh`, network access, or authentication as a
failure of the implementation itself.

### 5.2 Size and scope

Prefer one coherent review concern per PR.

Changed-line counts are heuristics, not hard correctness gates. A generated schema, fixture
set, lockfile, snapshot, or mechanical migration can legitimately be large.

If a change becomes difficult to verify or review as a unit, split it by dependency or behavior
rather than by an arbitrary line limit.

### 5.3 Description

When creating a PR, include:

- **What** changed.
- **Why** it changed.
- **How it was verified**, including exact commands when useful.
- **Risk and rollback** where material.
- **User-visible evidence** when relevant.
- Any **NOT RUN** or **BLOCKED** checks that matter to review.

Use a repository PR template when one exists.

### 5.4 Drafts

Draft PRs MAY be used when they improve collaboration or trigger useful CI early. They are not
mandatory for every agent task.

### 5.5 Review

Respect the repository's actual forge rules, CODEOWNERS, required checks, and approval policy.

This generic policy does **not** impose a universal human-approval count or prohibit
agent-to-agent review. A repository may require human review for sensitive paths; another may
allow automated review and auto-merge.

Codex MUST NOT fabricate an approval, dismiss a required reviewer, or bypass a protected rule.

### 5.6 Merge strategy

Use the merge strategy configured or requested for the repository.

When no stronger rule exists, squash merge is a sensible default for a single coherent PR.

Codex MUST NOT change repository merge settings, enable auto-merge globally, or merge a PR
unless the task authorizes the remote action.

---

## 6. Forge protections

Branch protection and repository rulesets are **remote governance controls**, not prerequisites
for local Codex execution.

Repositories SHOULD configure protections appropriate to their risk. Common controls include:

- required CI checks;
- secret scanning and push protection;
- blocked force pushes on integration branches;
- blocked branch deletion where appropriate;
- required review for sensitive areas;
- required conversation resolution where useful;
- CODEOWNERS for ownership-sensitive paths.

Do not hard-code universal check names such as `build`, `test`, `lint`, or `typecheck`; use the
checks the repository actually defines.

Signed commits, linear history, required approvals, administrator restrictions, and
"branch must be up to date" are governance options, not universal requirements. Enable them
only when they provide more value than friction for that repository.

Codex MUST NOT attempt to change protections or rulesets unless that is the explicit task.

---

## 7. Releases and versioning

### 7.1 Versioning

Use the repository's declared versioning policy.

For public artifacts that follow Semantic Versioning:

- **MAJOR** — incompatible public contract change.
- **MINOR** — backward-compatible capability.
- **PATCH** — backward-compatible bug fix.

Define what the repository considers public API.

### 7.2 Tags

Create or push release tags only when the task explicitly includes release work.

Recommended tag form for SemVer repositories:

```text
vMAJOR.MINOR.PATCH
```

Do not move or delete published release tags during routine work.

Tag signing is repository-specific. Codex MUST NOT enable signing, generate keys, or modify
global signing configuration as part of a normal implementation task.

### 7.3 Changelog

Follow the repository's changelog process. Do not hand-edit generated changelog sections when
the project regenerates them from commit or release metadata.

### 7.4 Hotfixes

A hotfix workflow is repository-specific. Prefer fixing the canonical integration line and then
backporting when the release process requires it.

Do not create release branches, cherry-pick across release lines, tag, or deploy unless the task
explicitly requests those actions.

---

## 8. Reverting and recovery

Prefer additive, auditable recovery over destructive history rewriting.

For an already shared bad commit, `git revert` is normally safer than reset plus force-push.

Before performing a revert, confirm the target commit and scope from repository evidence. Do
not infer a revert target from a stale plan or description.

Codex MUST NOT use destructive recovery commands merely to simplify its workspace.

If a requested recovery would overwrite unrelated local work, preserve that work and report the
conflict instead of cleaning it away.

---

## 9. Large files and generated artifacts

Use the repository's existing policy first.

General guidance:

- Do not add large binaries accidentally.
- Use Git LFS only when the repository already uses it or the operator explicitly requests it.
- Do not install or initialize Git LFS merely to satisfy a generic policy.
- Track application lockfiles when the ecosystem and repository expect them.
- Regenerate lockfiles with the project's package manager rather than editing them manually.
- Respect the existing `.gitignore` and `.gitattributes`.

Codex MUST NOT modify the user's global ignore file or global Git configuration as part of a
repository task.

Line-ending normalization is repository-specific. Do not introduce or rewrite `.gitattributes`
solely to impose a universal `eol=lf` policy unless the repository has decided to standardize
that behavior.

---

## 10. Secrets

### 10.1 Prevention

- Secrets MUST NOT be committed.
- Use environment variables, secret stores, or the repository's documented credential
  mechanism.
- Commit examples only with non-secret placeholder values.
- Respect existing ignore patterns for local credential files.
- Never print secrets into logs, summaries, patches, or commit messages.

Secret scanning SHOULD run in CI or forge-level protection when available.

A local scanner is useful but is **not** a universal prerequisite for Codex execution. Codex
must not install `gitleaks`, `trufflehog`, pre-commit frameworks, or system packages merely
because this generic policy mentions secret scanning.

### 10.2 If a secret is discovered

If Codex discovers a probable real credential:

1. do not echo the value;
2. avoid propagating it into new files, diffs, logs, or commits;
3. determine whether it is already tracked or shared;
4. report the affected path and credential type without reproducing the secret;
5. tell the operator that credential rotation may be required.

Credential rotation, access-log review, history purging, and cached-view invalidation are
external security actions and should be performed only with explicit authorization and the
required access.

Do not rewrite repository history automatically when a credential is found.

---

## 11. Signing and provenance

Commit and tag signing can be valuable, but it is environment-dependent and frequently
requires credentials or agents unavailable inside automated coding sessions.

Therefore:

- Commit signing is **not** a universal requirement for Codex-authored local work.
- Tag signing is required only when the repository's release process explicitly requires it.
- Codex MUST NOT change `user.signingkey`, `commit.gpgsign`, `tag.gpgsign`, `gpg.format`, SSH
  keys, GPG keys, or credential-agent configuration unless configuring signing is itself the
  requested task.
- If an explicitly required signature cannot be produced, complete the safe local work, mark
  the signing step `BLOCKED`, and do not claim provenance that was not created.
- Prefer CI attestations, protected merges, forge audit logs, and repository-level provenance
  controls when they fit the threat model.

Git identity should come from the existing environment. Do not invent an email address merely
to make a commit succeed.

---

## 12. Local Git configuration

Repository tasks SHOULD NOT mutate global Git configuration.

Codex MUST NOT run `git config --global ...` unless the explicit task is to configure the
operator's Git environment.

If repository behavior requires a Git setting, prefer:

1. a repository-local configuration that is safe to commit or document;
2. a command-line flag scoped to the current operation; or
3. a clear handoff note for the operator.

Useful global preferences such as `rerere`, `zdiff3`, `histogram`, default branch names, signing,
or global ignore files belong to the human/operator environment, not to generic automated
repository execution.

---

## 13. Automation and verification

Automation should make the repository easier for both humans and agents to verify.

### 13.1 CI is the authoritative shared gate

Where CI exists, shared enforcement belongs there.

Typical checks may include:

- formatting;
- linting;
- type checking;
- focused and full tests;
- security or secret scanning;
- dependency or vulnerability checks;
- schema or generated-file consistency;
- policy-specific validation.

Names and required checks are repository-specific.

### 13.2 Local hooks are optional acceleration

Pre-commit, Husky, Lefthook, and similar local hooks MAY provide fast feedback, but the generic
policy does not require them to be installed globally.

If the repository already supplies a deterministic bootstrap command and the task requires the
hooked tooling, Codex MAY use that repository-defined setup when allowed by the environment.

Do not turn a missing optional local hook into a blocker when equivalent repository checks can
be run directly or CI is the authoritative gate.

### 13.3 Verification behavior for agents

Codex SHOULD:

1. run the narrowest relevant checks first;
2. expand verification according to repository instructions and risk;
3. avoid real external API calls in unit-test layers unless the repository explicitly defines
   them as integration tests;
4. avoid modifying unrelated files simply to satisfy broad formatting tools;
5. report exact commands and outcomes when that information is useful for review.

If a full suite is unavailable or prohibitively environment-dependent, do not report it as
passing. Run what is available, identify the remaining gap, and preserve the evidence.

---

## 14. Exceptions and amendments

### 14.1 Task-local exceptions

If a rule cannot be followed because of the current environment or a more specific repository
workflow:

- prefer the more specific authoritative instruction;
- preserve safety and unrelated work;
- record the deviation in the final task summary;
- include it in the PR description if a PR is created.

A missing remote capability, signing key, human reviewer, or optional local tool is not by
itself a reason to abandon otherwise valid local work.

### 14.2 Policy amendments

Change this document through the repository's normal review process.

A policy that repeatedly requires exceptions should be revised rather than teaching agents to
work around it.

### 14.3 Emergencies

Production incident procedures may supersede normal workflow, but emergency authority should
be explicit. Preserve an audit trail and reconcile the resulting state after recovery.

---

## Appendix A: Agent-safe recipes

```bash
# Inspect state without mutating it
git status --short
git branch --show-current
git diff --stat
git diff --cached --stat

# Review the exact unstaged/staged changes
git diff
git diff --cached

# Check whitespace errors in the current diff
git diff --check

# Inspect recent history without changing it
git log --oneline --decorate -10

# Inspect divergence from an already-known local base ref
git log --oneline <base>..HEAD
git diff <base>...HEAD --stat

# Recover a known committed object without rewriting current history
git reflog
```

Commands that discard work, rewrite history, mutate global configuration, or contact remotes
are intentionally absent from the default agent recipe. Use them only when the active task
actually requires them.

---

## Appendix B: Decision table for Codex

| Situation | Default behavior |
|---|---|
| Dirty worktree with unrelated changes | Preserve them and continue if scopes do not overlap |
| Existing staged changes | Do not unstage or absorb them without task authority |
| Currently on `main` | Continue locally unless branch creation is required |
| No network access | Complete local work; mark remote actions `BLOCKED` or `NOT RUN` |
| `gh` missing | Do not install it automatically; provide a PR-ready handoff |
| Signing key unavailable | Do not change signing config; mark signing `BLOCKED` if required |
| Optional hook missing | Run equivalent repo-local checks when possible |
| Test dependency missing | Use documented bootstrap if allowed; otherwise report `BLOCKED` |
| Pre-existing commit history | Do not amend or rebase it |
| Remote push requested | Push only after local verification and authorization |
| Merge requested | Respect actual forge protections and required checks |
| Ambiguous destructive action | Do not guess; preserve state and report the blocker |

---

## Appendix C: Glossary

| Term | Meaning |
|---|---|
| **Canonical integration branch** | The repository's primary shared integration branch, usually `main`. |
| **Shared history** | Commits or refs another actor may already depend on. |
| **Local-first** | Complete safe repository-local work without making network access a prerequisite. |
| **Remote action** | An operation that changes or depends on a forge, remote Git server, external service, or credentialed system. |
| **Reviewable state** | A repository state whose intended changes, remaining gaps, and verification results can be inspected accurately. |
| **Verification evidence** | Commands, tests, checks, or artifacts that substantiate a claim about the change. |

---

## Appendix D: References

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/)
- [Semantic Versioning 2.0.0](https://semver.org/)
- [Pro Git](https://git-scm.com/book)
- OpenAI Codex documentation and repository-local `AGENTS.md` guidance should be consulted for
  current agent-execution behavior.
