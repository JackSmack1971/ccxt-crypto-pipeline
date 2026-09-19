"""Authoritative Solana runtime-configuration boundary.

Loads Helius adapter settings from YAML and resolves the runtime environment value
(the Helius API key) they name, via the shared `config.env` boundary. This module
must not import `helius.py` or `listener.py` -- those modules receive already-resolved
values from here instead of reading the environment themselves.
"""

from pathlib import Path
from typing import Any, Mapping

import yaml

from config.env import require_env, resolve_env

ROOT = Path(__file__).resolve().parents[2]


def load_config(root: Path = ROOT) -> dict[str, Any]:
    with (root / "config" / "solana.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_helius_api_key(
    root: Path = ROOT,
    *,
    strict: bool = True,
    config: dict[str, Any] | None = None,
    env_file: Path | None = None,
    process_env: Mapping[str, str] | None = None,
) -> str:
    """Resolve the Helius API key via the shared runtime-env boundary.

    Strict (default) resolution raises `MissingEnvironmentValueError` naming the
    configured `api_key_env` key before any network activity. Permissive resolution
    (`strict=False`) returns `""` instead, letting a caller represent Solana as not
    runnable without raising.
    """
    config = config if config is not None else load_config(root)
    env_name = config.get("api_key_env", "HELIUS_API_KEY")
    if strict:
        return require_env(env_name, env_file=env_file, process_env=process_env)
    return resolve_env(env_name, default="", env_file=env_file, process_env=process_env) or ""
