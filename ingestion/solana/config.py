"""Configuration for the Solana Tier 2 adapter."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(root: Path = ROOT) -> dict[str, Any]:
    with (root / "config" / "solana.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)
