"""Explicit, call-time runtime-environment resolution shared by EVM/Solana configuration.

Precedence per key: process environment > `.env` file > caller-supplied default.
Resolution happens only when `resolve_env`/`require_env` is called; importing this
module performs no environment or file reads, and no resolved value is cached.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env"


class MissingEnvironmentValueError(RuntimeError):
    def __init__(self, key: str):
        super().__init__(f"missing required environment value for {key!r}")
        self.key = key


def _dotenv_map(env_file: Path) -> Mapping[str, str]:
    if not env_file.is_file():
        return {}
    return {key: value for key, value in dotenv_values(env_file).items() if value is not None}


def resolve_env(
    key: str,
    *,
    default: str | None = None,
    env_file: Path | None = None,
    process_env: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve `key` at call time: process environment overrides `.env`, `.env` overrides `default`."""
    process = process_env if process_env is not None else os.environ
    if key in process:
        return process[key]
    file_values = _dotenv_map(env_file if env_file is not None else DEFAULT_ENV_FILE)
    if key in file_values:
        return file_values[key]
    return default


def require_env(
    key: str,
    *,
    env_file: Path | None = None,
    process_env: Mapping[str, str] | None = None,
) -> str:
    """Resolve `key` or raise, naming only the key — never any resolved value."""
    value = resolve_env(key, env_file=env_file, process_env=process_env)
    if not value:
        raise MissingEnvironmentValueError(key)
    return value
