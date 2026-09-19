"""Authoritative EVM runtime-configuration boundary.

Loads chain/provider settings from YAML and resolves the runtime environment values
(RPC URLs, explorer credentials) they name, via the shared `config.env` boundary. This
module must not import `rpc.py`, `providers.py`, or `listener.py` — those modules receive
already-resolved values from here instead of reading the environment themselves.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from config.env import require_env, resolve_env

ROOT = Path(__file__).resolve().parents[2]


def load_evm_config(root: Path = ROOT) -> dict[str, Any]:
    with (root / "config" / "evm.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_chain(chain: str, root: Path = ROOT) -> dict[str, Any]:
    with (root / "config" / "chains.yaml").open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    for item in data.get("networks", []):
        if item.get("name") == chain:
            if "chain_id" not in item or "rpc_env" not in item:
                raise ValueError(f"chain {chain!r} is not an EVM network")
            return {**{key: data[key] for key in ("confirmation_depth", "reorg_lookback_blocks")
                       if key in data}, **item}
    raise KeyError(f"unknown EVM chain {chain!r}")


def resolve_chain_rpc_url(
    chain: str,
    root: Path = ROOT,
    *,
    strict: bool = True,
    env_file: Path | None = None,
    process_env: Mapping[str, str] | None = None,
) -> str:
    """Resolve the RPC URL for a configured EVM chain via the shared runtime-env boundary.

    Strict (default) resolution raises `MissingEnvironmentValueError` naming the chain's
    `EVM_RPC_URL_*` key before any network activity. Permissive resolution (`strict=False`)
    returns `""` instead, letting a caller represent an unconfigured chain without raising.
    """
    env_name = load_chain(chain, root)["rpc_env"]
    if strict:
        return require_env(env_name, env_file=env_file, process_env=process_env)
    return resolve_env(env_name, default="", env_file=env_file, process_env=process_env) or ""


def resolve_explorer_credential(
    env_name: str,
    *,
    env_file: Path | None = None,
    process_env: Mapping[str, str] | None = None,
) -> str:
    """Resolve an explorer/indexer API key via the shared runtime-env boundary.

    Explorer credentials are independent of RPC availability and are optional for
    keyless-capable providers, so resolution never raises here.
    """
    return resolve_env(env_name, default="", env_file=env_file, process_env=process_env) or ""
