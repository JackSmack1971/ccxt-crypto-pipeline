#!/usr/bin/env bash
set -Eeuo pipefail
OSI_PREFIX="one-slice staging"
# shellcheck source-path=SCRIPTDIR source=lib_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_common.sh"
osi_install_trap

[ "$#" -eq 1 ] || osi_fail 64 "usage: stage_attributable.sh EVIDENCE_DIR"
evidence="$1"
[ -d "$evidence" ] || osi_fail 66 "evidence directory does not exist: $evidence"
[ -e "$evidence/captured" ] || osi_fail 65 "baseline capture is incomplete"
[ ! -e "$evidence/staged" ] || osi_fail 65 "staging already completed for this evidence directory"
root="$(cat "$evidence/repo-root")"
[ -d "$root" ] || osi_fail 66 "captured repository root no longer exists: $root"
cd "$root"

[ "$(git rev-parse HEAD)" = "$(cat "$evidence/head.before")" ] || osi_fail 74 "HEAD changed after baseline capture"
branch_now="$(git symbolic-ref -q --short HEAD || printf '%s' DETACHED)"
[ "$branch_now" = "$(cat "$evidence/branch.before")" ] || osi_fail 74 "branch identity changed after baseline capture"
pre_tree="$(cat "$evidence/index-tree.before")"
[ "$(git write-tree)" = "$pre_tree" ] || osi_fail 74 "real index changed after baseline capture; refusing to stage"

expected_index="$evidence/index.expected"
cp -p -- "$evidence/index.before" "$expected_index"
chmod u+w "$expected_index" 2>/dev/null || true
rm -rf "$evidence/patchwork"; mkdir -p "$evidence/patchwork"
: > "$evidence/agent-overlap.patch"

pathspecs=()

for rec in "$evidence"/candidates/*; do
  [ -d "$rec" ] || continue
  osi_read_z "$rec/path.z"; p="$OSI_PATH"
  ps=":(literal)$p"
  pathspecs+=("$ps")
  read -r tracked < "$rec/tracked"
  read -r pre_unstaged < "$rec/pre_unstaged"
  read -r before_type < "$rec/type.before"
  th="$(osi_type_hash "$p")"
  final_type="${th%%"$OSI_TAB"*}"
  printf '%s\n' "$final_type" > "$rec/type.final"
  printf '%s\n' "${th#*"$OSI_TAB"}" > "$rec/hash.final"

  if [ "$pre_unstaged" -eq 0 ]; then
    if [ "$tracked" -eq 0 ] && [ "$final_type" = absent ]; then
      continue   # declared but never created: nothing to attribute
    fi
    GIT_INDEX_FILE="$expected_index" git add -A -- "$ps"
    continue
  fi

  [ "$tracked" -eq 1 ] || osi_fail 79 "mixed ownership on untracked path is unsupported: $p"
  { [ "$before_type" = file ] && [ "$final_type" = file ]; } || osi_fail 79 "overlapping path changed type and cannot be isolated safely: $p"
  [ -f "$rec/worktree.before" ] || osi_fail 65 "missing working-tree baseline for overlapping path: $p"
  bx=0; ax=0
  if [ -x "$rec/worktree.before" ]; then bx=1; fi
  if [ -x "$p" ]; then ax=1; fi
  [ "$bx" = "$ax" ] || osi_fail 79 "overlapping path changed executable bit; cannot isolate mode change safely: $p"

  work="$evidence/patchwork/$(basename "$rec")"
  mkdir -p "$work/before" "$work/after" "$work/index"

  # Normalize both sides through the path's clean filters (eol, LFS, ...) so the
  # derived delta is expressed in index representation, not checkout bytes.
  before_blob="$(git hash-object -w --path="$p" -- "$rec/worktree.before")"
  after_blob="$(git hash-object -w --path="$p" -- "$p")"
  [ "$before_blob" != "$after_blob" ] || continue
  git cat-file blob "$before_blob" > "$work/before/f"
  git cat-file blob "$after_blob" > "$work/after/f"

  entry="$(GIT_INDEX_FILE="$expected_index" git ls-files -s -- "$ps")"
  idx_mode="${entry%% *}"; rest="${entry#* }"; idx_blob="${rest%% *}"
  git cat-file blob "$idx_blob" > "$work/index/f"

  # Fixed file names: the patch never contains the real path, so no quoting or
  # header rewriting is involved.
  diff_rc=0
  (cd "$work" && g diff --no-index --no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ -U3 -- before/f after/f) > "$work/agent.patch" || diff_rc=$?
  [ "$diff_rc" -eq 1 ] || osi_fail 70 "could not derive attributable diff for $p (rc=$diff_rc)"

  # Strict apply (-U3 context, no fuzz, no whitespace leniency) to a detached
  # copy of the captured index blob.
  if ! (cd "$work/index" && GIT_CEILING_DIRECTORIES="$work" g apply -p2 --whitespace=nowarn --no-ignore-whitespace ../agent.patch) 2>"$work/apply.err"; then
    osi_fail 79 "attributable hunk is too close to or dependent on pre-existing unstaged content: $p"
  fi
  new_blob="$(git hash-object -w --no-filters -- "$work/index/f")"
  printf '%s %s\t%s\0' "$idx_mode" "$new_blob" "$p" | GIT_INDEX_FILE="$expected_index" git update-index -z --index-info
  cat "$work/agent.patch" >> "$evidence/agent-overlap.patch"
done

[ "${#pathspecs[@]}" -gt 0 ] || osi_fail 65 "no candidate paths were captured"

expected_tree="$(GIT_INDEX_FILE="$expected_index" git write-tree)"
printf '%s\n' "$expected_tree" > "$evidence/index-tree.expected"
[ "$expected_tree" != "$pre_tree" ] || osi_fail 80 "no attributable index change exists after implementation"

# Reviewable evidence of exactly what will be staged.
g diff --no-ext-diff --binary --full-index "$pre_tree" "$expected_tree" -- "${pathspecs[@]}" > "$evidence/attributable.patch"

# ---- Every guard runs BEFORE the only real-index write. --------------------
osi_check_preservation "$evidence"
if ! g diff --no-ext-diff --check "$pre_tree" "$expected_tree" -- "${pathspecs[@]}" > "$evidence/whitespace.txt"; then
  osi_fail 86 "attributable delta fails whitespace check (see $evidence/whitespace.txt)"
fi

# Byte-exact index entries copied from the expected index. No patch is
# re-applied, so repository apply/whitespace configuration cannot alter content.
while IFS= read -r -d '' meta && IFS= read -r -d '' p; do
  read -r _om nm os ns st <<EOM
${meta#:}
EOM
  case "$st" in
    D) printf '0 %s\t%s\0' "$os" "$p" ;;
    *) printf '%s %s\t%s\0' "$nm" "$ns" "$p" ;;
  esac
done < <(g diff --raw -z --no-renames --no-abbrev "$pre_tree" "$expected_tree" -- "${pathspecs[@]}") > "$evidence/index-info.z"
[ -s "$evidence/index-info.z" ] || osi_fail 80 "expected index changed but no index entries were derived"
changed_paths="$(tr -cd '\000' < "$evidence/index-info.z" | wc -c | tr -d ' ')"

[ "$(git write-tree)" = "$pre_tree" ] || osi_fail 74 "real index changed while staging plan was being constructed"
if ! git update-index -z --index-info < "$evidence/index-info.z"; then
  [ "$(git write-tree 2>/dev/null || true)" = "$pre_tree" ] || osi_fail 82 "index update failed and the real index no longer matches the captured baseline"
  osi_fail 79 "index update failed; real index remains at captured baseline"
fi
[ "$(git write-tree)" = "$expected_tree" ] || osi_fail 82 "real index does not equal the mechanically constructed expected index"

: > "$evidence/staged"
printf 'staged attributable index delta: %s path(s)\n' "$changed_paths"
