# shellcheck shell=bash
# Shared helpers for one-slice-implementation scripts. Sourced, never executed.
# Targets bash 3.2+ (macOS /bin/bash): no associative arrays, no mapfile.

# Documented exit codes pass through; anything else becomes 90 (internal error).
osi_on_err() {
  local rc=$? line="${BASH_LINENO[0]}" cmd="$BASH_COMMAND"
  case "$rc" in 6[4-9]|7[0-9]|8[0-9]) exit "$rc" ;; esac
  printf '%s: internal error (exit %s) near line %s: %s\n' "$OSI_PREFIX" "$rc" "$line" "$cmd" >&2
  exit 90
}
osi_install_trap() { trap osi_on_err ERR; }

osi_fail() {
  local code="$1"; shift
  printf '%s: %s\n' "$OSI_PREFIX" "$*" >&2
  exit "$code"
}

# Git with configuration that could alter patch bytes, context matching, or
# path quoting pinned to safe values.
g() {
  git -c color.ui=never -c color.diff=never -c core.quotepath=false \
      -c diff.noprefix=false -c diff.mnemonicPrefix=false \
      -c apply.whitespace=nowarn -c apply.ignoreWhitespace=no "$@"
}

# Sets OSI_TYPE without forking.
osi_path_type() {
  if [ -L "$1" ]; then OSI_TYPE=symlink
  elif [ -f "$1" ]; then OSI_TYPE='file'
  elif [ -d "$1" ]; then OSI_TYPE=dir
  elif [ -e "$1" ]; then OSI_TYPE=other
  else OSI_TYPE=absent
  fi
}

# Prints type<TAB>hash for a path.
osi_type_hash() {
  local p="$1" h
  osi_path_type "$p"
  case "$OSI_TYPE" in
    file) h="$(git hash-object --no-filters -- "$p")" ;;
    symlink) h="$(readlink -- "$p" | git hash-object --stdin)" ;;
    absent) h=- ;;
    *) h="UNSUPPORTED:$OSI_TYPE" ;;
  esac
  printf '%s\t%s\n' "$OSI_TYPE" "$h"
}

# Delimited membership sets (bash 3.2 has no associative arrays).
OSI_SEP=$'\037'
# shellcheck disable=SC2034  # used by sourcing scripts
OSI_TAB=$'\t'
osi_set_add() { eval "$1=\"\${$1}\$2\$OSI_SEP\""; }
osi_set_has() {
  local set="$1" needle="$2"
  case "$needle" in *"$OSI_SEP"*) return 1 ;; esac
  case "$OSI_SEP$set" in *"$OSI_SEP$needle$OSI_SEP"*) return 0 ;; esac
  return 1
}

osi_read_z() { IFS= read -r -d '' OSI_PATH < "$1" || true; }

# Loads candidate paths into OSI_CANDIDATES (delimited set).
osi_load_candidates() {
  local evidence="$1" rec
  OSI_CANDIDATES=""
  for rec in "$evidence"/candidates/*; do
    [ -d "$rec" ] || continue
    osi_read_z "$rec/path.z"
    osi_set_add OSI_CANDIDATES "$OSI_PATH"
  done
}

# Proves pre-existing unrelated work is byte/type identical and that no new
# unrelated unstaged/untracked path appeared. Runs before the real-index write
# (stage) and again after it (verify). Requires cwd = repo root.
osi_check_preservation() {
  local evidence="$1" rec origin expected actual p
  local pre_unstaged="" pre_untracked="" now_untracked=""
  osi_load_candidates "$evidence"

  for rec in "$evidence"/preserve/*; do
    [ -d "$rec" ] || continue
    osi_read_z "$rec/path.z"; p="$OSI_PATH"
    read -r origin < "$rec/origin"
    case "$origin" in
      unstaged) osi_set_add pre_unstaged "$p" ;;
      untracked) osi_set_add pre_untracked "$p" ;;
    esac
  done

  while IFS= read -r -d '' p; do osi_set_add now_untracked "$p"; done \
    < <(git ls-files --others --exclude-standard -z)

  for rec in "$evidence"/preserve/*; do
    [ -d "$rec" ] || continue
    osi_read_z "$rec/path.z"; p="$OSI_PATH"
    osi_set_has "$OSI_CANDIDATES" "$p" && continue
    read -r origin < "$rec/origin"
    read -r expected < "$rec/type"; read -r actual < "$rec/hash"
    expected="$expected$OSI_TAB$actual"
    actual="$(osi_type_hash "$p")"
    [ "$actual" = "$expected" ] || osi_fail 84 "pre-existing unrelated path changed (type/content): $p"
    if [ "$origin" = untracked ] && ! osi_set_has "$now_untracked" "$p"; then
      osi_fail 84 "pre-existing untracked path is no longer untracked: $p"
    fi
  done

  while IFS= read -r -d '' p; do
    osi_set_has "$OSI_CANDIDATES" "$p" && continue
    osi_set_has "$pre_unstaged" "$p" || osi_fail 85 "new unrelated unstaged path appeared: $p"
  done < <(git diff --name-only -z --no-renames)

  while IFS= read -r -d '' p; do
    osi_set_has "$OSI_CANDIDATES" "$p" && continue
    osi_set_has "$pre_untracked" "$p" || osi_fail 85 "new unrelated untracked path appeared (verification byproduct?): $p"
  done < <(git ls-files --others --exclude-standard -z)
}
