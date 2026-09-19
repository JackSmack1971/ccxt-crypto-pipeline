"""Orchestrate the Phase 1 ingestion jobs and expose one-shot cycle execution."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler

from ingestion.cex.common import load_config as load_cex_config
from ingestion.cex.refresh import refresh_exchange
from ingestion.cex.universe import discover_universe
from ingestion.dex.tier0.poller import load_config as load_chain_config, poll
from ingestion.evm.config import resolve_chain_rpc_url
from ingestion.evm.listener import run_once as run_evm_once
from ingestion.solana.config import load_config as load_solana_config, resolve_helius_api_key
from ingestion.solana.listener import run_once as run_solana_once
from normalization.reconcile import reconcile_assets
from storage.db import (classify_provider_failure, log_run_end, log_run_start,
                        record_provider_observation, safe_error_message)

_DAY_SECONDS = 86400.0
_MINUTE_SECONDS = 60.0


@dataclass
class JobResult:
    job_name: str
    status: str
    rows_written: int = 0
    error: str | None = None


@dataclass
class CycleResult:
    started_at: datetime
    finished_at: datetime | None = None
    jobs: list[JobResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(job.status in {"success", "skipped"} for job in self.jobs)


class Pipeline:
    """Thin coordinator around the existing one-pass ingestion functions."""

    def __init__(self, *, db_path: str = "storage/pipeline.duckdb",
                 cex_config_path: str = "config/cex.yaml",
                 chains_config_path: str = "config/chains.yaml",
                 solana_config_path: str = "config/solana.yaml"):
        self.db_path = db_path
        self.cex_config_path = cex_config_path
        self.chains_config_path = chains_config_path
        self.solana_config_path = solana_config_path

    def run_job(self, name: str, operation: Callable[[], int], *,
               expected_interval_seconds: float | None = None) -> JobResult:
        run_id = log_run_start(f"scheduler:{name}", self.db_path)
        started = time.monotonic()
        try:
            rows = int(operation() or 0)
        except Exception as exc:
            message = safe_error_message(exc)
            log_run_end(run_id, "failed", self.db_path, error_message=message)
            record_provider_observation(
                name, name, classify_provider_failure(message), self.db_path,
                latency_ms=(time.monotonic() - started) * 1000,
                expected_interval_seconds=expected_interval_seconds,
                error_message=message, run_id=run_id,
            )
            return JobResult(name, "failed", error=message)
        log_run_end(run_id, "success", self.db_path, rows_written=rows)
        record_provider_observation(
            name, name, "success", self.db_path,
            latency_ms=(time.monotonic() - started) * 1000,
            expected_interval_seconds=expected_interval_seconds,
            rows_observed=rows, run_id=run_id,
        )
        return JobResult(name, "success", rows_written=rows)

    def expected_job_intervals(self) -> dict[str, float]:
        """Configured poll cadence per job, in seconds, for offline quality-SLO comparison."""
        chains = load_chain_config(self.chains_config_path)
        tier0_minutes = max(15, min(30, int(chains.get("poll_interval_minutes", 20))))
        return {
            "cex_refresh": _DAY_SECONDS,
            "tier0_poll": tier0_minutes * _MINUTE_SECONDS,
            "evm_listeners": _MINUTE_SECONDS,
            "solana_listener": _MINUTE_SECONDS,
            "normalization": _DAY_SECONDS,
        }

    def cex_refresh(self) -> int:
        config = load_cex_config(self.cex_config_path)
        discover_universe(config, db_path=self.db_path)
        return sum(refresh_exchange(exchange, config=config, db_path=self.db_path)
                   for exchange in config.get("exchanges", []))

    def tier0_poll(self) -> int:
        return poll(self.chains_config_path, db_path=self.db_path)

    def evm_listeners(self) -> int:
        """Poll every configured EVM chain, recording a per-chain quality observation.

        Each chain is isolated: one chain's failure is recorded under its own
        `evm_rpc`/chain-name scope and does not prevent the remaining
        configured chains from being attempted in the same cycle.
        """
        config = load_chain_config(self.chains_config_path)
        total = 0
        for chain in config.get("networks", []):
            name, env_name = chain.get("name"), chain.get("rpc_env")
            if not (name and env_name and resolve_chain_rpc_url(name, strict=False)):
                continue
            lookback = int(chain.get("evm_lookback_blocks", config.get("evm_lookback_blocks", 1900)))
            started = time.monotonic()
            try:
                rows = run_evm_once(name, db_path=self.db_path, lookback_blocks=lookback)
            except Exception as exc:
                message = safe_error_message(exc)
                record_provider_observation(
                    "evm_rpc", name, classify_provider_failure(message), self.db_path,
                    latency_ms=(time.monotonic() - started) * 1000,
                    expected_interval_seconds=_MINUTE_SECONDS, error_message=message,
                )
                continue
            record_provider_observation(
                "evm_rpc", name, "success", self.db_path,
                latency_ms=(time.monotonic() - started) * 1000,
                expected_interval_seconds=_MINUTE_SECONDS, rows_observed=rows,
            )
            total += rows
        return total

    def solana_listener(self) -> int:
        root = Path(self.solana_config_path).resolve().parents[1]
        config = load_solana_config(root)
        if not resolve_helius_api_key(root, strict=False, config=config):
            return 0
        return run_solana_once(db_path=self.db_path, config=config,
                               expected_interval_seconds=_MINUTE_SECONDS)

    def normalize(self) -> int:
        return len(reconcile_assets(self.db_path))

    def run_cycle(self) -> CycleResult:
        result = CycleResult(started_at=datetime.now(timezone.utc))
        intervals = self.expected_job_intervals()
        for name, operation in (("cex_refresh", self.cex_refresh),
                                ("tier0_poll", self.tier0_poll),
                                ("evm_listeners", self.evm_listeners),
                                ("solana_listener", self.solana_listener),
                                ("normalization", self.normalize)):
            result.jobs.append(self.run_job(name, operation, expected_interval_seconds=intervals.get(name)))
        result.finished_at = datetime.now(timezone.utc)
        return result


def build_scheduler(pipeline: Pipeline | None = None) -> BlockingScheduler:
    pipeline = pipeline or Pipeline()
    chains = load_chain_config(pipeline.chains_config_path)
    interval = max(15, min(30, int(chains.get("poll_interval_minutes", 20))))
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(pipeline.run_job, "interval", days=1, id="cex_refresh",
                      args=["cex_refresh", pipeline.cex_refresh],
                      max_instances=1, coalesce=True)
    scheduler.add_job(pipeline.run_job, "interval", minutes=interval, id="tier0_poll",
                      args=["tier0_poll", pipeline.tier0_poll],
                      max_instances=1, coalesce=True)
    scheduler.add_job(pipeline.run_job, "interval", minutes=1, id="evm_listeners",
                      args=["evm_listeners", pipeline.evm_listeners],
                      max_instances=1, coalesce=True)
    scheduler.add_job(pipeline.run_job, "interval", minutes=1, id="solana_listener",
                      args=["solana_listener", pipeline.solana_listener],
                      max_instances=1, coalesce=True)
    scheduler.add_job(pipeline.run_job, "cron", hour=2, minute=0, id="normalization",
                      args=["normalization", pipeline.normalize],
                      max_instances=1, coalesce=True)
    return scheduler
