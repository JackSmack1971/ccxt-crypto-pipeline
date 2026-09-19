import ast
import importlib
import sys
from pathlib import Path

import pytest

from config.env import MissingEnvironmentValueError, require_env, resolve_env

REPO_ROOT = Path(__file__).resolve().parents[1]

# The shared runtime-env boundary itself; every other module must resolve
# environment values through `resolve_env`/`require_env` instead of reading
# `os.getenv`/`os.environ` directly.
ALLOWED_DIRECT_ENV_ACCESS_MODULES = {
    REPO_ROOT / "config" / "env.py",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "node_modules",
}


def _iter_repo_python_files():
    for path in REPO_ROOT.rglob("*.py"):
        parts = path.relative_to(REPO_ROOT).parts
        if any(part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info") for part in parts):
            continue
        yield path


def _is_os_getenv_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "getenv"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
    )


def _is_os_environ_node(node):
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _is_os_environ_get_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _is_os_environ_node(node.func.value)
    )


def _is_os_environ_subscript(node):
    return isinstance(node, ast.Subscript) and _is_os_environ_node(node.value)


def _direct_env_access_lines(source: str) -> list[int]:
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if _is_os_getenv_call(node) or _is_os_environ_get_call(node) or _is_os_environ_subscript(node):
            violations.append(node.lineno)
    return violations


def write_env_file(tmp_path, contents):
    env_file = tmp_path / ".env"
    env_file.write_text(contents, encoding="utf-8")
    return env_file


def test_no_direct_environment_reads_outside_shared_runtime_env_boundary():
    offenders = {}
    for path in _iter_repo_python_files():
        if path in ALLOWED_DIRECT_ENV_ACCESS_MODULES:
            continue
        source = path.read_text(encoding="utf-8")
        lines = _direct_env_access_lines(source)
        if lines:
            offenders[str(path.relative_to(REPO_ROOT))] = lines
    assert offenders == {}, (
        "os.getenv/os.environ.get/os.environ[...] must only be used inside "
        f"the shared config.env runtime-env boundary; found direct access in: {offenders}"
    )


def test_env_example_declares_exactly_the_supported_keys():
    env_example = REPO_ROOT / ".env.example"
    declared_keys = {
        line.split("=", 1)[0].strip()
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert declared_keys == {
        "ETHERSCAN_API_KEY",
        "ROUTESCAN_API_KEY",
        "HELIUS_API_KEY",
        "EVM_RPC_URL_ETHEREUM",
        "EVM_RPC_URL_BASE",
        "EVM_RPC_URL_ARBITRUM",
        "EVM_RPC_URL_BSC",
    }
    assert "MEGANODE_API_KEY" not in env_example.read_text(encoding="utf-8")


def test_gitignore_ignores_dotenv_files_but_preserves_dotenv_example(tmp_path):
    import subprocess

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env\n" in gitignore or gitignore.rstrip("\n").endswith(".env")
    assert ".env.*" in gitignore
    assert "!.env.example" in gitignore

    for name, expect_ignored in (
        (".env", True),
        (".env.local", True),
        (".env.example", False),
    ):
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "--quiet", name],
            check=False,
        )
        assert (result.returncode == 0) == expect_ignored, name


def test_resolve_env_falls_back_to_default_when_unset_everywhere(tmp_path):
    env_file = write_env_file(tmp_path, "")
    assert resolve_env("MISSING_KEY", default="fallback", env_file=env_file, process_env={}) == "fallback"


def test_resolve_env_reads_dotenv_value_when_process_env_unset(tmp_path):
    env_file = write_env_file(tmp_path, "HELIUS_API_KEY=from-dotenv\n")
    value = resolve_env("HELIUS_API_KEY", env_file=env_file, process_env={})
    assert value == "from-dotenv"


def test_process_environment_overrides_dotenv_value(tmp_path):
    env_file = write_env_file(tmp_path, "HELIUS_API_KEY=from-dotenv\n")
    value = resolve_env(
        "HELIUS_API_KEY", env_file=env_file, process_env={"HELIUS_API_KEY": "from-process"}
    )
    assert value == "from-process"


def test_repeated_resolution_is_deterministic(tmp_path):
    env_file = write_env_file(tmp_path, "ETHERSCAN_API_KEY=stable-value\n")
    first = resolve_env("ETHERSCAN_API_KEY", env_file=env_file, process_env={})
    second = resolve_env("ETHERSCAN_API_KEY", env_file=env_file, process_env={})
    assert first == second == "stable-value"


def test_require_env_returns_resolved_value(tmp_path):
    env_file = write_env_file(tmp_path, "")
    value = require_env("EVM_RPC_URL_BASE", env_file=env_file, process_env={"EVM_RPC_URL_BASE": "https://rpc.example"})
    assert value == "https://rpc.example"


def test_require_env_raises_naming_key_but_never_a_credential_value(tmp_path):
    env_file = write_env_file(tmp_path, "")
    secret_value = "sk-super-secret-should-never-leak"
    with pytest.raises(MissingEnvironmentValueError) as excinfo:
        require_env("ROUTESCAN_API_KEY", env_file=env_file, process_env={})
    message = str(excinfo.value)
    assert "ROUTESCAN_API_KEY" in message
    assert secret_value not in message


def test_require_env_treats_empty_value_as_missing(tmp_path):
    env_file = write_env_file(tmp_path, "MEGANODE_API_KEY=\n")
    with pytest.raises(MissingEnvironmentValueError):
        require_env("MEGANODE_API_KEY", env_file=env_file, process_env={})


def test_importing_config_env_performs_no_environment_reads(monkeypatch):
    sys.modules.pop("config.env", None)

    def fail_getenv(*args, **kwargs):
        raise AssertionError("import must not read os.environ")

    def fail_dotenv_values(*args, **kwargs):
        raise AssertionError("import must not read the .env file")

    monkeypatch.setattr("os.getenv", fail_getenv)
    monkeypatch.setattr("dotenv.dotenv_values", fail_dotenv_values)

    module = importlib.import_module("config.env")

    assert hasattr(module, "resolve_env")
    sys.modules.pop("config.env", None)


def test_module_has_no_resolved_value_cache(tmp_path):
    import config.env as env_module

    env_file = write_env_file(tmp_path, "HELIUS_API_KEY=first-value\n")
    assert resolve_env("HELIUS_API_KEY", env_file=env_file, process_env={}) == "first-value"

    env_file.write_text("HELIUS_API_KEY=second-value\n", encoding="utf-8")
    assert resolve_env("HELIUS_API_KEY", env_file=env_file, process_env={}) == "second-value"

    module_state = {
        name for name in vars(env_module) if "cache" in name.lower() and not name.startswith("__")
    }
    assert module_state == set()


def test_resolve_env_does_not_mutate_process_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("HELIUS_API_KEY", raising=False)
    env_file = write_env_file(tmp_path, "HELIUS_API_KEY=from-dotenv\n")

    import os

    resolve_env("HELIUS_API_KEY", env_file=env_file)

    assert "HELIUS_API_KEY" not in os.environ
