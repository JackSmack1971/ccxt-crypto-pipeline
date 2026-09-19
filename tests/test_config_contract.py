import importlib
import sys

import pytest

from config.env import MissingEnvironmentValueError, require_env, resolve_env


def write_env_file(tmp_path, contents):
    env_file = tmp_path / ".env"
    env_file.write_text(contents, encoding="utf-8")
    return env_file


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
