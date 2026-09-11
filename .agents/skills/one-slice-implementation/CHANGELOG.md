# Changelog

## 1.2.0

Measured with `tests/run_scenarios.sh` (23 throwaway-repo scenarios), `tests/perf.sh`,
and `tests/objects_readonly.sh`. Scenario results for 1.1.0 → 1.2.0: 9/23 → 23/23 PASS
(bash 5.2.21 and bash 3.2.57, Git 2.43.0).

### Fixed: real index mutated before a blocking failure
- Preservation, byproduct, and whitespace guards now run before the single real-index
  write; previously they ran in `verify_index.sh`, after staging had already changed the
  index (S06, S07).
- The real-index write copies exact mode/blob entries via `git update-index --index-info`
  instead of re-applying a patch, so `apply.whitespace=fix` can no longer rewrite staged
  content (S08, previously exit 82).
- Whitespace check is scoped to this run's delta; pre-existing staged user work is no
  longer checked (S06, previously a false exit 86).

### Fixed: false blocks
- Same-file overlap is computed after the path's clean filters, so CRLF/`autocrlf`
  checkouts isolate correctly (S09).
- Overlap patches use fixed temp file names; non-ASCII and quoted paths no longer break
  header rewriting (S10).
- Git config that changes diff output is pinned: `color.ui`, `diff.noprefix`,
  `diff.mnemonicPrefix`, `core.quotepath`, `apply.*` (S15, S16).
- Duplicate candidate arguments are recorded once (S21).

### Fixed: crashes with undocumented exit codes
- Declared-but-never-created path is skipped (S05, previously raw exit 128).
- Unresolved conflict anywhere in the index blocks at preflight with `76` (S11, previously
  raw 128 at capture).
- Gitignored new candidate blocks at capture with `81` (S12, previously raw 1 after editing).
- Any other unexpected failure exits `90` with the failing line and command.

### Fixed: preflight gap
- Preflight probes the object store as well as the index lock. A linked worktree with a
  read-only object store now blocks at preflight with `77`; 1.1.0 passed preflight and
  crashed in staging after the edit.
- Preflight also refuses bisect and sequencer state.

### Performance
- `verify_index.sh` membership checks are in-process instead of per-path file scans.
  Verify time with pre-existing untracked files: 50 → 2.49s vs 0.14s; 100 → 8.70s vs 0.27s;
  200 → 33.34s vs 0.53s. 1.2.0 at 2,000 files: 7.03s (linear).

### Added
- `baseline.sh --extend` registers a path discovered mid-run, accepting only provably
  untouched paths (S18–S20).
- Exit-code table in `references/GIT_ATTRIBUTION.md`, linked from the terminal-status table.
- Terminal-status row for "no eligible slice".
- `lib_common.sh` shared helpers; `tests/` harness.

### Changed (SKILL.md)
- Helpers are invoked as `<skill-dir>/scripts/...`; a repository's own `scripts/` can no
  longer shadow them.
- Preflight prints the evidence directory and the agent copies it verbatim, instead of
  relying on a shell variable persisting between commands.
- Escalation authorization covers all helpers, not just preflight.
- Verification byproducts must go outside the repo or into ignored paths.
- `SKILL.md` 1,508 → 1,775 words; `references/GIT_ATTRIBUTION.md` 779 → 1,280 words.

### Script quality
- `shellcheck -S style` clean (1.1.0 had SC2318: lock path built from a global, not the
  function parameter).

## 1.1.0
- Initial version reviewed.
