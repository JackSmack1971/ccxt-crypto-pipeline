#!/usr/bin/env python3
"""Mechanical guardrails for storage-schema migrations.

The guard does not replace repository tests. It checks a small set of invariants that
are easy for an agent to miss: SCHEMA_VERSION movement, storage/test surface changes,
obvious direct network calls in changed Python tests, and optional DuckDB schema
convergence between a fresh and migrated database.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

VERSION_RE = re.compile(
    r"^\s*SCHEMA_VERSION(?:\s*:\s*[^=]+)?\s*=\s*(?P<value>[^#\n]+?)\s*$"
)
NETWORK_MODULES = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib.request",
    "http.client",
    "urllib3",
    "ccxt",
    "web3",
    "solana.rpc",
}
NETWORK_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "request",
    "urlopen",
    "fetch",
    "fetch_ohlcv",
    "fetch_ticker",
    "fetch_tickers",
    "fetch_markets",
    "fetchMarkets",
    "fetchTickers",
    "fetchOHLCV",
}
URL_RE = re.compile(r"https?://", re.IGNORECASE)


@dataclass
class Finding:
    level: str
    code: str
    message: str


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return proc.stdout


def parse_literal(text: str) -> Any:
    text = text.strip()
    try:
        return ast.literal_eval(text)
    except Exception:
        return text


def scan_schema_versions_in_text(path: str, text: str) -> list[tuple[str, Any]]:
    hits: list[tuple[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = VERSION_RE.match(line)
        if match:
            hits.append((f"{path}:{line_no}", parse_literal(match.group("value"))))
    return hits


def current_schema_versions(repo: Path) -> list[tuple[str, Any]]:
    storage = repo / "storage"
    if not storage.is_dir():
        return []
    hits: list[tuple[str, Any]] = []
    for path in storage.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".sql"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(repo).as_posix()
        hits.extend(scan_schema_versions_in_text(rel, text))
    return hits


def base_schema_versions(repo: Path, base_ref: str) -> list[tuple[str, Any]]:
    files = run_git(repo, "ls-tree", "-r", "--name-only", base_ref, "--", "storage")
    hits: list[tuple[str, Any]] = []
    for rel in files.splitlines():
        if Path(rel).suffix not in {".py", ".sql"}:
            continue
        proc = subprocess.run(
            ["git", "-C", str(repo), "show", f"{base_ref}:{rel}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode == 0:
            hits.extend(scan_schema_versions_in_text(rel, proc.stdout))
    return hits


def numeric_version(value: Any) -> tuple[int, ...] | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return (value,)
    if isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)*", value.strip()):
        return tuple(int(part) for part in value.strip().split("."))
    return None


def changed_files(repo: Path, base_ref: str) -> list[str]:
    tracked = run_git(repo, "diff", "--name-only", base_ref, "--")
    untracked = run_git(repo, "ls-files", "--others", "--exclude-standard")
    paths = {line.strip() for line in (tracked + "\n" + untracked).splitlines() if line.strip()}
    return sorted(paths)


def dotted_root(node: ast.AST) -> tuple[str | None, str | None]:
    if not isinstance(node, ast.Attribute):
        return None, None
    method = node.attr
    cur: ast.AST = node.value
    parts: list[str] = []
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts)), method
    return None, method


def network_calls_in_test(path: Path) -> tuple[list[str], bool]:
    text = path.read_text(encoding="utf-8")
    has_url = bool(URL_RE.search(text))
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [f"cannot parse changed test: {exc}"], has_url

    module_aliases: dict[str, str] = {}
    direct_aliases: dict[str, str] = {}
    network_objects: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name
                if root in NETWORK_MODULES or any(root.startswith(m + ".") for m in NETWORK_MODULES):
                    module_aliases[alias.asname or root.split(".")[0]] = root
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in NETWORK_MODULES or any(module.startswith(m + ".") for m in NETWORK_MODULES):
                for alias in node.names:
                    direct_aliases[alias.asname or alias.name] = f"{module}.{alias.name}"

    # Track common client/session/exchange objects created from imported network modules.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
            continue
        root, _ = dotted_root(value.func)
        if root is None:
            continue
        root_head = root.split(".")[0]
        if root_head not in module_aliases:
            continue
        targets: list[ast.expr] = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                network_objects.add(target.id)

    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in direct_aliases:
            hits.append(f"line {node.lineno}: direct network-capable call {direct_aliases[node.func.id]}()")
            continue
        if isinstance(node.func, ast.Attribute):
            root, method = dotted_root(node.func)
            if root is None or method is None:
                continue
            root_head = root.split(".")[0]
            imported_module = module_aliases.get(root_head)
            if imported_module and method in NETWORK_METHODS:
                hits.append(f"line {node.lineno}: direct network-capable call {root}.{method}()")
            elif root_head in network_objects and (method in NETWORK_METHODS or method.startswith("fetch")):
                hits.append(f"line {node.lineno}: network-client call {root}.{method}()")
    return hits, has_url


def normalize_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return [normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): normalize_value(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    return value


def duckdb_signature(db_path: Path) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore
    except ImportError as exc:
        raise RuntimeError("duckdb is required for --fresh-db/--migrated-db comparison") from exc

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        columns = conn.execute(
            """
            SELECT table_schema, table_name, ordinal_position, column_name,
                   data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name, ordinal_position
            """
        ).fetchall()
        constraints = conn.execute(
            """
            SELECT schema_name, table_name, constraint_type, constraint_text,
                   constraint_column_names, referenced_table, referenced_column_names
            FROM duckdb_constraints()
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
            ORDER BY schema_name, table_name, constraint_type, constraint_text
            """
        ).fetchall()
        return {
            "columns": [normalize_value(list(row)) for row in columns],
            "constraints": [normalize_value(list(row)) for row in constraints],
        }
    finally:
        conn.close()


def add(findings: list[Finding], level: str, code: str, message: str) -> None:
    findings.append(Finding(level, code, message))


def evaluate(args: argparse.Namespace) -> tuple[list[Finding], dict[str, Any]]:
    repo = Path(args.repo).resolve()
    findings: list[Finding] = []
    details: dict[str, Any] = {"repo": str(repo), "base_ref": args.base_ref}

    try:
        inside = run_git(repo, "rev-parse", "--is-inside-work-tree").strip().lower()
    except RuntimeError as exc:
        add(findings, "ERROR", "git-missing", f"repository is not a usable Git work tree: {exc}")
        return findings, details
    if inside != "true":
        add(findings, "ERROR", "git-missing", "repository is not inside a Git work tree")
        return findings, details
    if not (repo / "storage").is_dir():
        add(findings, "ERROR", "storage-missing", "expected /storage directory is missing")
        return findings, details

    try:
        changed = changed_files(repo, args.base_ref)
        base_versions = base_schema_versions(repo, args.base_ref)
    except RuntimeError as exc:
        add(findings, "ERROR", "git-base-invalid", str(exc))
        return findings, details

    current_versions = current_schema_versions(repo)
    details["changed_files"] = changed
    details["base_schema_versions"] = base_versions
    details["current_schema_versions"] = current_versions

    if len(base_versions) != 1:
        add(findings, "ERROR", "base-version-authority", f"expected exactly one SCHEMA_VERSION at {args.base_ref}, found {len(base_versions)}")
    if len(current_versions) != 1:
        add(findings, "ERROR", "current-version-authority", f"expected exactly one current SCHEMA_VERSION, found {len(current_versions)}")
    if len(base_versions) == 1 and len(current_versions) == 1:
        old = base_versions[0][1]
        new = current_versions[0][1]
        if old == new:
            add(findings, "ERROR", "version-not-bumped", f"SCHEMA_VERSION is unchanged at {new!r}")
        else:
            old_num = numeric_version(old)
            new_num = numeric_version(new)
            if old_num is not None and new_num is not None:
                if new_num <= old_num:
                    add(findings, "ERROR", "version-not-advanced", f"SCHEMA_VERSION moved from {old!r} to {new!r}, which is not an advance")
                else:
                    add(findings, "INFO", "version-advanced", f"SCHEMA_VERSION advanced from {old!r} to {new!r}")
            else:
                add(findings, "WARN", "version-order-opaque", f"SCHEMA_VERSION changed from {old!r} to {new!r}; guard cannot prove monotonic ordering")

    storage_changed = [p for p in changed if p == "storage" or p.startswith("storage/")]
    if not storage_changed:
        add(findings, "ERROR", "storage-not-changed", "no /storage file differs from the selected pre-migration base")
    else:
        add(findings, "INFO", "storage-changed", f"{len(storage_changed)} storage path(s) changed")

    db_path = repo / "storage" / "db.py"
    if not db_path.is_file():
        add(findings, "ERROR", "db-accessor-missing", "storage/db.py is missing")
    elif "storage/db.py" not in changed:
        add(findings, "WARN", "db-accessor-unchanged", "storage/db.py is unchanged; require round-trip evidence that accessors remain compatible")
    else:
        add(findings, "INFO", "db-accessor-changed", "storage/db.py changed with the migration")

    changed_tests = [p for p in changed if p.endswith(".py") and (p.startswith("tests/") or "/tests/" in p)]
    details["changed_tests"] = changed_tests
    if not changed_tests:
        add(findings, "ERROR", "tests-not-changed", "no changed Python tests were found for the migration")
    for rel in changed_tests:
        path = repo / rel
        if not path.exists():
            continue
        hits, has_url = network_calls_in_test(path)
        for hit in hits:
            add(findings, "ERROR", "live-network-test", f"{rel}: {hit}; storage migration tests must use fixtures only")
        if has_url:
            add(findings, "WARN", "url-in-test", f"{rel} contains an http(s) URL; verify it is inert fixture text and not used for live I/O")

    if bool(args.fresh_db) != bool(args.migrated_db):
        add(findings, "ERROR", "db-compare-pair", "provide both --fresh-db and --migrated-db, or neither")
    elif args.fresh_db and args.migrated_db:
        fresh = Path(args.fresh_db).resolve()
        migrated = Path(args.migrated_db).resolve()
        if not fresh.is_file() or not migrated.is_file():
            add(findings, "ERROR", "db-compare-missing", "fresh or migrated DuckDB file does not exist")
        else:
            try:
                fresh_sig = duckdb_signature(fresh)
                migrated_sig = duckdb_signature(migrated)
                details["fresh_schema"] = fresh_sig
                details["migrated_schema"] = migrated_sig
                if fresh_sig != migrated_sig:
                    add(findings, "ERROR", "schema-divergence", "fresh and migrated DuckDB catalog signatures differ")
                else:
                    add(findings, "INFO", "schema-converged", "fresh and migrated DuckDB catalog signatures match")
            except Exception as exc:
                add(findings, "ERROR", "db-compare-failed", str(exc))

    return findings, details


def render(findings: Iterable[Finding]) -> None:
    for finding in findings:
        print(f"[{finding.level}] {finding.code}: {finding.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mechanical invariants for a /storage schema migration")
    parser.add_argument("--repo", default=".", help="target repository root")
    parser.add_argument("--base-ref", default="HEAD", help="Git ref representing the pre-migration state")
    parser.add_argument("--fresh-db", help="freshly initialized target DuckDB file")
    parser.add_argument("--migrated-db", help="DuckDB file upgraded from the prior schema")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    findings, details = evaluate(args)
    if args.json:
        print(json.dumps({"findings": [asdict(f) for f in findings], "details": details}, indent=2, default=str))
    else:
        render(findings)

    return 1 if any(f.level == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
