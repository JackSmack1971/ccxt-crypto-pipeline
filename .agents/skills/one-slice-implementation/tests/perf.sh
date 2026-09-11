#!/usr/bin/env bash
# Times capture/stage/verify vs. count of pre-existing untracked (non-ignored) files.
# Usage: tests/perf.sh [SKILL_DIR] N [N ...]
set -uo pipefail
if [ -d "${1:-}" ]; then SKILL_DIR="$(cd "$1" && pwd)"; shift; else SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"; fi
S="$SKILL_DIR/scripts"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t GIT_CONFIG_GLOBAL=/dev/null
now() { date +%s.%N; }
for n in "$@"; do
  d="$(mktemp -d)"; cd "$d" || exit 1
  git init -q -b main .; seq 1 40 > a.txt; git add .; git commit -qm i
  mkdir u; for i in $(seq 1 "$n"); do printf '%s\n' "$i" > "u/f$i.txt"; done
  ev="$("$S/baseline.sh" --preflight)"
  t0=$(now); "$S/baseline.sh" --capture "$ev" -- a.txt >/dev/null; t1=$(now)
  sed -i '5s/.*/AGENT/' a.txt; "$S/stage_attributable.sh" "$ev" >/dev/null; t2=$(now)
  "$S/verify_index.sh" "$ev" >/dev/null; rc=$?; t3=$(now)
  awk -v n="$n" -v a="$t0" -v b="$t1" -v c="$t2" -v e="$t3" -v rc="$rc" \
    'BEGIN{printf "untracked=%-5s capture=%6.2fs stage=%6.2fs verify=%7.2fs (rc=%s)\n", n, b-a, c-b, e-c, rc}'
done
