#!/usr/bin/env bash
set -Eeuo pipefail
OSI_PREFIX="one-slice baseline"
# shellcheck source-path=SCRIPTDIR source=lib_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_common.sh"
osi_install_trap

usage() {
  cat >&2 <<'USAGE'
Usage:
  baseline.sh --preflight
  baseline.sh --capture EVIDENCE_DIR -- path [path ...]
  baseline.sh --extend  EVIDENCE_DIR -- path [path ...]   (untouched paths only; before staging)
USAGE
  exit 64
}

repo_root() { git rev-parse --show-toplevel 2>/dev/null || osi_fail 69 "not inside a Git worktree"; }

abs_git_path() {
  local root="$1" p
  p="$(git rev-parse --git-path "$2" 2>/dev/null)" || osi_fail 69 "cannot resolve Git path: $2"
  case "$p" in /*) printf '%s\n' "$p" ;; *) printf '%s/%s\n' "$root" "$p" ;; esac
}

probe_index_lock() {
  local index_path="$1"
  local lock="${index_path}.lock"
  [ ! -e "$lock" ] || osi_fail 75 "Git index lock already exists (another Git process running, or stale lock): $lock"
  umask 077
  ( set -C; : > "$lock" ) 2>/dev/null || osi_fail 77 "Git index is not writable (cannot create $lock)"
  rm -f -- "$lock" 2>/dev/null || osi_fail 77 "created Git index lock probe but could not remove it: $lock"
}

# Staging writes blobs into the object store, which linked worktrees share and
# which can carry different sandbox permissions than the index.
probe_object_store() {
  local objdir="$1" probe
  probe="$(mktemp "$objdir/one-slice-probe.XXXXXX" 2>/dev/null)" || osi_fail 77 "Git object store is not writable: $objdir"
  rm -f -- "$probe" 2>/dev/null || osi_fail 77 "created object-store probe but could not remove it: $probe"
}

check_repo_state() {
  local p gp
  for p in MERGE_HEAD REBASE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
    gp="$(git rev-parse --git-path "$p")"
    [ ! -e "$gp" ] || osi_fail 76 "unrelated Git operation appears to be in progress ($p)"
  done
  for p in rebase-merge rebase-apply sequencer; do
    gp="$(git rev-parse --git-path "$p")"
    [ ! -d "$gp" ] || osi_fail 76 "Git operation in progress ($p)"
  done
  if [ -n "$(git ls-files -u)" ]; then
    osi_fail 76 "index contains unresolved conflict entries; resolve them before running"
  fi
}

validate_rel_path() {
  local p="$1"
  [ -n "$p" ] || osi_fail 64 "empty candidate path"
  case "$p" in
    /*|./*|../*|*/../*|*/..|*/./*|.|..|*//*|*/)
      osi_fail 64 "candidate paths must be normalized repo-root-relative file paths: $p" ;;
    *[$'\n\t\r"\\']*|*"$OSI_SEP"*)
      osi_fail 64 "candidate path contains a character the attribution scripts do not support: $p" ;;
  esac
}

record_preserve() {
  local dir="$1" origin="$2" p="$3" rec th
  rec="$dir/preserve/$(printf '%06d' "$PRESERVE_N")"
  mkdir "$rec"
  printf '%s\0' "$p" > "$rec/path.z"
  printf '%s\n' "$origin" > "$rec/origin"
  th="$(osi_type_hash "$p")"
  printf '%s\n' "${th%%"$OSI_TAB"*}" > "$rec/type"
  printf '%s\n' "${th#*"$OSI_TAB"}" > "$rec/hash"
  PRESERVE_N=$((PRESERVE_N + 1))
}

capture_preservation_set() {
  local dir="$1" p
  mkdir -p "$dir/preserve"; PRESERVE_N=0
  while IFS= read -r -d '' p; do record_preserve "$dir" unstaged "$p"; done < <(git diff --name-only -z --no-renames)
  while IFS= read -r -d '' p; do record_preserve "$dir" staged "$p"; done < <(git diff --cached --name-only -z --no-renames)
  while IFS= read -r -d '' p; do record_preserve "$dir" untracked "$p"; done < <(git ls-files --others --exclude-standard -z)
  printf '%s\n' "$PRESERVE_N" > "$dir/preserve.count"
}

capture_candidate() {
  local dir="$1" p="$2" mode="$3" n rec ps tracked=0 pre_staged=0 pre_unstaged=0 t
  validate_rel_path "$p"
  ps=":(literal)$p"
  osi_load_candidates "$dir"
  if osi_set_has "$OSI_CANDIDATES" "$p"; then return 0; fi

  if [ -n "$(git ls-files --cached -- "$ps")" ]; then tracked=1; fi
  if [ "$tracked" -eq 0 ] && [ -n "$(git ls-files --others --exclude-standard -- "$ps")" ]; then
    osi_fail 78 "candidate is a pre-existing untracked path and cannot be safely attributed: $p"
  fi
  if [ "$tracked" -eq 0 ] && git check-ignore -q --no-index -- "$p"; then
    osi_fail 81 "candidate is gitignored; ignored paths are not staged by this workflow: $p"
  fi
  if [ -n "$(git ls-files -u -- "$ps")" ]; then osi_fail 76 "candidate has unresolved index stages: $p"; fi
  if ! git diff --cached --quiet -- "$ps"; then pre_staged=1; fi
  if ! git diff --quiet -- "$ps"; then pre_unstaged=1; fi
  osi_path_type "$p"; t="$OSI_TYPE"
  [ "$t" != dir ] || osi_fail 64 "candidate must be a file path, not a directory: $p"

  if [ "$mode" = extend ]; then
    # A path added mid-run must be provably untouched: absent and never recorded
    # as pre-existing work, or tracked with no staged/unstaged delta. Any edit made
    # before extension, and any user-owned work, makes it ineligible.
    for rec in "$dir"/preserve/*; do
      [ -d "$rec" ] || continue
      osi_read_z "$rec/path.z"
      [ "$OSI_PATH" != "$p" ] || osi_fail 78 "cannot extend with a path that held pre-existing work: $p"
    done
    if [ "$tracked" -eq 1 ]; then
      { [ "$pre_staged" -eq 0 ] && [ "$pre_unstaged" -eq 0 ]; } || osi_fail 78 "cannot extend with a tracked path that is already modified: $p"
    else
      [ "$t" = absent ] || osi_fail 78 "cannot extend with an untracked path that already exists: $p"
    fi
  fi

  if [ "$tracked" -eq 1 ] && [ "$pre_unstaged" -eq 1 ]; then
    [ "$t" = file ] || osi_fail 79 "pre-existing unstaged overlap is only supported for regular text files: $p ($t)"
    if git diff --numstat -- "$ps" | awk -F '\t' '$1=="-" && $2=="-" {found=1} END{exit !found}'; then
      osi_fail 79 "pre-existing binary overlap cannot be partially attributed safely: $p"
    fi
  fi

  read -r n < "$dir/candidate.count"
  rec="$dir/candidates/$(printf '%06d' "$n")"
  mkdir -p "$rec"
  printf '%s\0' "$p" > "$rec/path.z"
  printf '%s\n' "$tracked" > "$rec/tracked"
  printf '%s\n' "$pre_staged" > "$rec/pre_staged"
  printf '%s\n' "$pre_unstaged" > "$rec/pre_unstaged"
  printf '%s\n' "$t" > "$rec/type.before"
  git ls-files --stage -- "$ps" > "$rec/index.before.txt"
  if [ "$t" = file ]; then cp -p -- "$p" "$rec/worktree.before"; fi
  if [ "$t" = symlink ]; then readlink -- "$p" > "$rec/symlink.before"; fi
  printf '%s\n' "$((n + 1))" > "$dir/candidate.count"
}

[ "$#" -ge 1 ] || usage
mode="$1"; shift
root="$(repo_root)"
cd "$root"
index_path="$(abs_git_path "$root" index)"

case "$mode" in
  --preflight)
    [ "$#" -eq 0 ] || usage
    git rev-parse --verify HEAD >/dev/null 2>&1 || osi_fail 69 "repository must have a valid HEAD"
    check_repo_state
    probe_index_lock "$index_path"
    probe_object_store "$(abs_git_path "$root" objects)"
    evidence="$(mktemp -d "${TMPDIR:-/tmp}/one-slice-implementation.XXXXXX")" || osi_fail 73 "cannot create run-local evidence directory"
    chmod 700 "$evidence" 2>/dev/null || true
    printf '%s\n' "$root" > "$evidence/repo-root"
    printf '%s\n' "$index_path" > "$evidence/index-path"
    git rev-parse HEAD > "$evidence/head.preflight"
    printf '%s\n' "$evidence"
    ;;

  --capture|--extend)
    [ "$#" -ge 3 ] || usage
    evidence="$1"; shift
    [ "$1" = "--" ] || usage
    shift
    [ -d "$evidence" ] || osi_fail 66 "evidence directory does not exist: $evidence"
    [ "$(cat "$evidence/repo-root" 2>/dev/null || true)" = "$root" ] || osi_fail 66 "evidence directory belongs to a different repository"

    if [ "$mode" = --capture ]; then
      [ ! -e "$evidence/captured" ] || osi_fail 65 "baseline already captured in $evidence (use --extend for newly discovered paths)"
      check_repo_state
      probe_index_lock "$index_path"
      [ -f "$index_path" ] || osi_fail 69 "Git index file does not exist: $index_path"
      cp -p -- "$index_path" "$evidence/index.before"
      GIT_INDEX_FILE="$evidence/index.before" git write-tree > "$evidence/index-tree.before"
      git rev-parse HEAD > "$evidence/head.before"
      git symbolic-ref -q --short HEAD > "$evidence/branch.before" || printf '%s\n' DETACHED > "$evidence/branch.before"
      git status --porcelain=v1 -z --untracked-files=all > "$evidence/status.before.z"
      mkdir -p "$evidence/candidates"
      printf '0\n' > "$evidence/candidate.count"
      capture_preservation_set "$evidence"
      for p in "$@"; do capture_candidate "$evidence" "$p" capture; done
      : > "$evidence/captured"
      printf 'baseline captured: %s candidate path(s); %s pre-existing path(s) preserved\n' "$(cat "$evidence/candidate.count")" "$PRESERVE_N"
    else
      [ -e "$evidence/captured" ] || osi_fail 65 "run --capture before --extend"
      [ ! -e "$evidence/staged" ] || osi_fail 65 "cannot extend after staging"
      [ "$(git write-tree)" = "$(cat "$evidence/index-tree.before")" ] || osi_fail 74 "real index changed after baseline capture"
      for p in "$@"; do capture_candidate "$evidence" "$p" extend; done
      printf 'baseline extended: %s candidate path(s) total\n' "$(cat "$evidence/candidate.count")"
    fi
    ;;

  *) usage ;;
esac
