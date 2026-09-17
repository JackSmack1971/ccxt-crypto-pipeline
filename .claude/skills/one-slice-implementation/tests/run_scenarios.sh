#!/usr/bin/env bash
# Adversarial scenario harness for one-slice-implementation helper scripts.
# Usage: tests/run_scenarios.sh [SKILL_DIR]   (default: parent of this tests/ dir)
# Builds throwaway repos under mktemp. For each scenario it records the failing
# step, exit code, whether the REAL index was mutated on a non-success path, and
# whether pre-existing user work survived.
set -uo pipefail
SKILL_DIR="$(cd "${1:-$(dirname "$0")/..}" && pwd)"
S="$SKILL_DIR/scripts"
WORK="$(mktemp -d)"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export GIT_CONFIG_GLOBAL=/dev/null
RESULTS="$WORK/results.tsv"
printf 'id\tscenario\texpected\tstep\texit\tindex_mutated_on_fail\tuser_work_ok\tverdict\n' > "$RESULTS"

new_repo() {
  local d="$WORK/$1"; rm -rf "$d"; mkdir -p "$d"; cd "$d" || exit 1
  git init -q -b main .
  seq 1 40 > a.txt; seq 1 40 > b.txt; printf 'x\n' > c.txt
  git add . && git commit -qm init
}

# run_flow ID NAME EXPECTED CANDIDATES...   (edits come from function `edit`)
# EXPECTED: COMPLETE | BLOCK_PRE_EDIT | BLOCK_CLEAN (fails at stage/verify with the
# real index exactly as handed to staging)
run_flow() {
  local id="$1" name="$2" expected="$3"; shift 3
  local ev step="" rc=0 tree_before tree_after mutated="n/a" userok="yes" verdict
  ev="$("$S/baseline.sh" --preflight 2>"$WORK/$id.err")"; rc=$?
  if [ $rc -ne 0 ]; then step=preflight; else
    "$S/baseline.sh" --capture "$ev" -- "$@" >/dev/null 2>>"$WORK/$id.err"; rc=$?
    if [ $rc -ne 0 ]; then step=capture; else
      edit
      tree_before="$(git write-tree 2>/dev/null || echo WRITE_TREE_FAILED)"
      "$S/stage_attributable.sh" "$ev" >/dev/null 2>>"$WORK/$id.err"; rc=$?
      if [ $rc -ne 0 ]; then step=stage; else
        "$S/verify_index.sh" "$ev" >/dev/null 2>>"$WORK/$id.err"; rc=$?
        if [ $rc -ne 0 ]; then step=verify; else step="done"; fi
      fi
      if [ "$step" != "done" ]; then
        tree_after="$(git write-tree 2>/dev/null || echo WRITE_TREE_FAILED)"
        if [ "$tree_after" = "$tree_before" ]; then mutated=no; else mutated=YES; fi
      fi
    fi
  fi
  if declare -F user_check >/dev/null; then user_check || userok=NO; fi
  case "$expected:$step:$mutated" in
    "COMPLETE:done:"*) verdict=PASS ;;
    BLOCK_PRE_EDIT:preflight:*|BLOCK_PRE_EDIT:capture:*) verdict=PASS ;;
    BLOCK_CLEAN:stage:no|BLOCK_CLEAN:verify:no) verdict=PASS ;;
    *) verdict=FAIL ;;
  esac
  # Undocumented exit codes (raw git/bash failures) are a defect on any path.
  case "$rc" in 0|6[4-6]|69|70|7[3-9]|8[0-6]) ;; *) verdict="FAIL(raw-exit)" ;; esac
  [ "$userok" = yes ] || verdict=FAIL
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$name" "$expected" "$step" "$rc" "$mutated" "$userok" "$verdict" >> "$RESULTS"
  unset -f edit user_check
}

# ---------------------------------------------------------------- scenarios
new_repo s01
edit() { sed -i '5s/.*/AGENT/' a.txt; printf 'new\n' > d.txt; }
run_flow S01 "happy path: modify tracked + create new" COMPLETE a.txt d.txt

new_repo s02
sed -i '1s/.*/USER_UNSTAGED/' b.txt; printf 'USER_STAGED\n' >> c.txt; git add c.txt; printf 'u\n' > user_untracked.txt
edit() { sed -i '5s/.*/AGENT/' a.txt; }
user_check() { grep -q USER_UNSTAGED b.txt && git diff --cached --name-only | grep -q c.txt && [ -f user_untracked.txt ] && ! git diff --cached --name-only | grep -q b.txt; }
run_flow S02 "unrelated staged/unstaged/untracked preserved" COMPLETE a.txt

new_repo s03
sed -i '1s/.*/USER/' a.txt
edit() { sed -i '30s/.*/AGENT/' a.txt; }
user_check() { ! git diff --cached a.txt | grep -q '^+USER' && git diff --cached a.txt | grep -q '^+AGENT'; }
run_flow S03 "same-file overlap, distant hunks" COMPLETE a.txt

new_repo s04
sed -i '10s/.*/USER/' a.txt
edit() { sed -i '12s/.*/AGENT/' a.txt; }
user_check() { grep -q USER a.txt; }
run_flow S04 "same-file overlap, adjacent hunks (fail closed)" BLOCK_CLEAN a.txt

new_repo s05
edit() { sed -i '5s/.*/AGENT/' a.txt; }   # declared e.txt, never created it
run_flow S05 "over-declared candidate never created" COMPLETE a.txt e.txt

new_repo s06
printf 'trailing   \n' >> c.txt; git add c.txt   # user's pre-existing staged whitespace
edit() { sed -i '5s/.*/AGENT/' a.txt; }
run_flow S06 "user's pre-staged whitespace, unrelated file" COMPLETE a.txt

new_repo s07
edit() { sed -i '5s/.*/AGENT/' a.txt; printf 'cov\n' > coverage.xml; }   # test byproduct
run_flow S07 "undeclared untracked byproduct (coverage.xml)" BLOCK_CLEAN a.txt

new_repo s08
git config apply.whitespace fix
edit() { sed -i '5s/.*/AGENT   /' a.txt; }
run_flow S08 "apply.whitespace=fix + agent trailing ws" BLOCK_CLEAN a.txt

new_repo s09
printf '* text=auto\n' > .gitattributes; git add .gitattributes; git commit -qm attrs
git config core.autocrlf true
sed -i 's/$/\r/' a.txt   # CRLF working tree as on a Windows checkout
git add --renormalize . >/dev/null 2>&1; git reset -q
sed -i '1s/.*/USER\r/' a.txt
edit() { sed -i '30s/.*/AGENT\r/' a.txt; }
user_check() { git diff --cached -- a.txt | grep -q '^+AGENT' && ! git diff --cached -- a.txt | grep -q 'USER' && grep -q USER a.txt; }
run_flow S09 "CRLF checkout (autocrlf), distant overlap" COMPLETE a.txt

new_repo s10
mkdir -p src; seq 1 40 > 'src/café.txt'; git add . && git commit -qm u
sed -i '1s/.*/USER/' 'src/café.txt'
edit() { sed -i '35s/.*/AGENT/' 'src/café.txt'; }
user_check() { git diff --cached | grep -q '^+AGENT' && ! git diff --cached | grep -q USER; }
run_flow S10 "non-ASCII filename, distant overlap" COMPLETE 'src/café.txt'

new_repo s11
git checkout -q -b other; printf 'other\n' > c.txt; git commit -qam o; git checkout -q main
printf 'mine\n' > c.txt; git stash -q; git checkout -q other; git stash pop -q >/dev/null 2>&1 || true
edit() { sed -i '5s/.*/AGENT/' a.txt; }
run_flow S11 "unmerged entry in unrelated path" BLOCK_PRE_EDIT a.txt

new_repo s12
printf 'dist/\n' > .gitignore; git add .gitignore; git commit -qm ig
edit() { mkdir -p dist; printf 'gen\n' > dist/out.js; }
run_flow S12 "declared new path is gitignored" BLOCK_PRE_EDIT dist/out.js

new_repo s13
edit() { sed -i '5s/.*/AGENT/' a.txt; printf 'y\n' > c.txt; git add c.txt; }  # concurrent index change
run_flow S13 "index changed after capture" BLOCK_CLEAN a.txt

new_repo s14
touch "$(git rev-parse --git-path index).lock"
edit() { :; }
run_flow S14 "stale index.lock present" BLOCK_PRE_EDIT a.txt

new_repo s15
git config color.ui always
edit() { sed -i '5s/.*/AGENT/' a.txt; }
run_flow S15 "config color.ui=always, happy path" COMPLETE a.txt

new_repo s16
git config diff.noprefix true
sed -i '1s/.*/USER/' a.txt
edit() { sed -i '30s/.*/AGENT/' a.txt; }
user_check() { git diff --cached -- a.txt | grep -q '^+AGENT' && ! git diff --cached -- a.txt | grep -q 'USER' && grep -q USER a.txt; }
run_flow S16 "config diff.noprefix=true, distant overlap" COMPLETE a.txt

new_repo s17main
git worktree add -q ../s17wt -b wt
cd "$WORK/s17wt" || exit 1
sed -i '1s/.*/USER/' b.txt
edit() { sed -i '5s/.*/AGENT/' a.txt; }
user_check() { grep -q USER b.txt && ! git diff --cached --name-only | grep -q b.txt; }
run_flow S17 "linked worktree (index under .git/worktrees)" COMPLETE a.txt

new_repo s18
edit() { sed -i '5s/.*/AGENT/' a.txt; "$S/baseline.sh" --extend "$ev" -- helper/new.txt >/dev/null 2>>"$WORK/S18.err" && { mkdir -p helper; printf 'h\n' > helper/new.txt; }; }
user_check() { git diff --cached --name-only | grep -q '^helper/new.txt$'; }
run_flow S18 "--extend newly discovered path before creating" COMPLETE a.txt

new_repo s19
edit() { sed -i '5s/.*/AGENT/' a.txt; sed -i '3s/.*/AGENT/' b.txt; "$S/baseline.sh" --extend "$ev" -- b.txt >/dev/null 2>>"$WORK/S19.err"; echo $? > "$WORK/s19.extend_rc"; }
user_check() { [ "$(cat "$WORK/s19.extend_rc")" = 78 ]; }
run_flow S19 "--extend refuses path already edited" BLOCK_CLEAN a.txt

new_repo s20
sed -i '1s/.*/USER/' b.txt
edit() { sed -i '5s/.*/AGENT/' a.txt; "$S/baseline.sh" --extend "$ev" -- b.txt >/dev/null 2>>"$WORK/S20.err"; echo $? > "$WORK/s20.extend_rc"; }
user_check() { [ "$(cat "$WORK/s20.extend_rc")" = 78 ] && grep -q USER b.txt && ! git diff --cached --name-only | grep -q b.txt; }
run_flow S20 "--extend refuses path holding user work" COMPLETE a.txt

new_repo s21
sed -i '1s/.*/USER/' a.txt
edit() { sed -i '30s/.*/AGENT/' a.txt; }
user_check() { git diff --cached -- a.txt | grep -q '^+AGENT' && ! git diff --cached -- a.txt | grep -q 'USER' && grep -q USER a.txt; }
run_flow S21 "duplicate candidate arg on overlapping path" COMPLETE a.txt a.txt

new_repo s22
edit() { rm c.txt; }
run_flow S22 "agent deletes a tracked file" COMPLETE c.txt

new_repo s23
seq 1 40 > 'my notes.txt'; git add . && git commit -qm sp
sed -i '1s/.*/USER/' 'my notes.txt'
edit() { sed -i '30s/.*/AGENT/' 'my notes.txt'; }
user_check() { grep -q USER 'my notes.txt' && ! git diff --cached | grep -q '^+USER'; }
run_flow S23 "filename with space, distant overlap" COMPLETE 'my notes.txt'

# ---------------------------------------------------------------- report
awk -F'\t' '{printf "%-4s | %-48s | %-14s | %-9s | %-4s | %-8s | %-4s | %s\n",$1,$2,$3,$4,$5,$6,$7,$8}' "$RESULTS"
pass="$(awk -F'\t' 'NR>1 && $8=="PASS"' "$RESULTS" | wc -l | tr -d ' ')"
total="$(awk 'NR>1' "$RESULTS" | wc -l | tr -d ' ')"
printf '\nTOTAL: %s/%s PASS   (stderr logs: %s/*.err)\n' "$pass" "$total" "$WORK"
[ "$pass" = "$total" ]
