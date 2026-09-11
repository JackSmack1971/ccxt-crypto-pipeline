#!/usr/bin/env bash
set -Eeuo pipefail
OSI_PREFIX="one-slice verify-index"
# shellcheck source-path=SCRIPTDIR source=lib_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_common.sh"
osi_install_trap

[ "$#" -eq 1 ] || osi_fail 64 "usage: verify_index.sh EVIDENCE_DIR"
evidence="$1"
[ -d "$evidence" ] || osi_fail 66 "evidence directory does not exist: $evidence"
[ -e "$evidence/captured" ] || osi_fail 65 "baseline capture is incomplete"
[ -e "$evidence/staged" ] || osi_fail 65 "attributable staging has not completed"
[ -f "$evidence/index-tree.expected" ] || osi_fail 65 "expected index tree is missing"
root="$(cat "$evidence/repo-root")"
cd "$root"

[ "$(git rev-parse HEAD)" = "$(cat "$evidence/head.before")" ] || osi_fail 74 "HEAD changed after baseline capture"
branch_now="$(git symbolic-ref -q --short HEAD || printf '%s' DETACHED)"
[ "$branch_now" = "$(cat "$evidence/branch.before")" ] || osi_fail 74 "branch identity changed after baseline capture"

pre_tree="$(cat "$evidence/index-tree.before")"
expected_tree="$(cat "$evidence/index-tree.expected")"
[ "$(git write-tree)" = "$expected_tree" ] || osi_fail 82 "real index tree differs from expected attributable index tree"

pathspecs=()
for rec in "$evidence"/candidates/*; do
  [ -d "$rec" ] || continue
  osi_read_z "$rec/path.z"; p="$OSI_PATH"
  pathspecs+=(":(literal)$p")
  read -r et < "$rec/type.final"; read -r eh < "$rec/hash.final"
  [ "$(osi_type_hash "$p")" = "$et$OSI_TAB$eh" ] || osi_fail 83 "candidate changed after staging: $p"
done

osi_check_preservation "$evidence"

# Whitespace check scoped to this run's delta, never to pre-existing staged work.
g diff --no-ext-diff --check "$pre_tree" "$expected_tree" -- "${pathspecs[@]}" >/dev/null || osi_fail 86 "attributable delta fails whitespace check"

: > "$evidence/verified"
printf 'index verified: exact expected tree; unrelated pre-existing work preserved\n'
