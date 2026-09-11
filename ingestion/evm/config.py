"""Load EVM chain/provider settings without embedding deployment values in code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


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
            return item
    raise KeyError(f"unknown EVM chain {chain!r}")
