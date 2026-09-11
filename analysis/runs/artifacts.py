from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from analysis.backtesting.simulator import BacktestResult
from analysis.datasets.snapshot import DatasetSnapshot
from analysis.metrics.core import compute_metrics


def _dump(value: Any) -> bytes:
    return (json.dumps(value, default=str, sort_keys=True, separators=(",", ":")) + "\n").encode()


_SECRET_KEY = re.compile(r"(?:api[_-]?key|credential|password|secret|token|rpc[_-]?url)$", re.IGNORECASE)
_SECRET_VALUE = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+|(?:api[_-]?key|token|secret|password|private[_-]?key)\s*[:=]\s*)[^\s,;]+"
)
_URL_CREDENTIAL = re.compile(r"(?i)(://)[^/\s:@]+:[^/\s@]+@")


def _sanitized(value: Any, key: str = "") -> Any:
    """Keep provenance while preventing conventional credential fields from leaking."""
    if _SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): _sanitized(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitized(item) for item in value]
    if isinstance(value, str):
        value = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", value)
        return _SECRET_VALUE.sub(r"\1[REDACTED]", value)
    return value


def _sanitized_error(error: Exception) -> str:
    message = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", str(error))
    return re.sub(r"(?i)(api[_-]?key|credential|password|secret|token|rpc[_-]?url)\s*[:=]\s*[^\s,;]+",
                  r"\1=[REDACTED]", message)


def write_run(result: BacktestResult, dataset: DatasetSnapshot, strategy: Any, output_dir: str | Path,
              *, strategy_config: dict[str, Any] | None = None, code_version: str = "local") -> Path:
    """Write immutable normalized ledgers and a manifest; refuse conflicting rewrites."""
    strategy_config = strategy_config or {}
    inputs = {"dataset_identity": dataset.dataset_identity, "query_policy_version": dataset.policy.query_policy_version,
              "timeframe": dataset.policy.timeframe, "start": str(dataset.policy.start), "end": str(dataset.policy.end),
              "sources": list(dataset.policy.sources), "asset_ids": list(dataset.policy.asset_ids),
              "strategy": {"name": strategy.name, "version": strategy.version, "config": _sanitized(strategy_config)},
              "simulator": asdict(result.config), "code_version": code_version}
    run_id = hashlib.sha256(_dump(inputs)).hexdigest()[:24]
    target = Path(output_dir) / run_id
    target.mkdir(parents=True, exist_ok=True)
    artifacts = {"trades.json": list(result.trades), "orders.json": list(result.orders),
                 "equity.json": list(result.equity), "metrics.json": compute_metrics(result.equity, trades=result.trades)}
    manifest = {"manifest_version": "phase2-v1", "run_id": run_id, "immutable": True, "inputs": inputs,
                "artifacts": {name: hashlib.sha256(_dump(value)).hexdigest() for name, value in artifacts.items()}}
    for name, value in {**artifacts, "manifest.json": manifest}.items():
        path = target / name
        content = _dump(value)
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"immutable run artifact differs: {path}")
        if not path.exists():
            path.write_bytes(content)
    return target


def write_failed_run(output_dir: str | Path, inputs: dict[str, Any], error: Exception) -> Path:
    """Record a deterministic local rejection without fabricating result ledgers."""
    payload = {"manifest_version": "phase2-v1", "status": "failed", "inputs": _sanitized(inputs),
               "error_type": type(error).__name__, "error": _sanitized_error(error)}
    run_id = hashlib.sha256(_dump(payload)).hexdigest()[:24]
    target = Path(output_dir) / run_id
    target.mkdir(parents=True, exist_ok=True)
    path = target / "manifest.json"
    content = _dump({**payload, "run_id": run_id, "immutable": True})
    if path.exists() and path.read_bytes() != content:
        raise FileExistsError(f"immutable failed-run artifact differs: {path}")
    if not path.exists():
        path.write_bytes(content)
    return target
