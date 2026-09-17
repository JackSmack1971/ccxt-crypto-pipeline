#!/usr/bin/env bash
# Linked worktree whose index dir is writable but whose shared object store is not.
# Requires root (uses runuser to drop to 'nobody'). Usage: tests/objects_readonly.sh [SKILL_DIR]
# Expected: preflight exits 77 before any edit.
set -u
SK="$(cd "${1:-$(dirname "$0")/..}" && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "skip: requires root"; exit 0; }
base="$(mktemp -d)"; chmod 755 "$base"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t GIT_CONFIG_GLOBAL=/dev/null
cd "$base" && git init -q -b main main && cd main && seq 1 40 > a.txt && git add . && git commit -qm i && git worktree add -q ../wt -b wt
chown -R nobody "$base"; chown -R root "$base/main/.git/objects"; chmod -R a+rX "$base/main/.git/objects"
cp -r "$SK" "$base/skill"; chmod -R a+rX "$base/skill"
runuser -u nobody -- env HOME="$base" TMPDIR="$base" BASE="$base" GIT_CONFIG_NOSYSTEM=1 bash -c '
  export GIT_CONFIG_GLOBAL="$BASE/gitconfig"; git config --global --add safe.directory "*"
  cd "$BASE/wt"
  ev="$("$BASE/skill/scripts/baseline.sh" --preflight)"; rc=$?; echo "preflight rc=$rc"
  [ $rc -eq 0 ] || exit 0
  "$BASE/skill/scripts/baseline.sh" --capture "$ev" -- a.txt >/dev/null; echo "capture rc=$?"
  sed -i "5s/.*/AGENT/" a.txt; echo "(edit made)"
  "$BASE/skill/scripts/stage_attributable.sh" "$ev" >/dev/null; echo "stage rc=$?"
' 2>&1
