"""Orchestrate the Phase 1 ingestion jobs and expose one-shot cycle execution."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler

from ingestion.cex.common import load_config as load_cex_config
from ingestion.cex.refresh import refresh_exchange
from ingestion.cex.universe import discover_universe
from ingestion.dex.tier0.poller import load_config as load_chain_config, poll
from ingestion.evm.listener import run_once as run_evm_once
from ingestion.solana.config import load_config as load_solana_config
from ingestion.solana.listener import run_once as run_solana_once
from normalization.reconcile import reconcile_assets
from storage.db import log_run_end, log_run_start, safe_error_message


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

    def run_job(self, name: str, operation: Callable[[], int]) -> JobResult:
        run_id = log_run_start(f"scheduler:{name}", self.db_path)
        try:
            rows = int(operation() or 0)
        except Exception as exc:
            message = safe_error_message(exc)
            log_run_end(run_id, "failed", self.db_path, error_message=message)
            return JobResult(name, "failed", error=message)
        log_run_end(run_id, "success", self.db_path, rows_written=rows)
        return JobResult(name, "success", rows_written=rows)

    def cex_refresh(self) -> int:
        config = load_cex_config(self.cex_config_path)
        discover_universe(config, db_path=self.db_path)
        return sum(refresh_exchange(exchange, config=config, db_path=self.db_path)
                   for exchange in config.get("exchanges", []))

    def tier0_poll(self) -> int:
        return poll(self.chains_config_path, db_path=self.db_path)

    def evm_listeners(self) -> int:
        config = load_chain_config(self.chains_config_path)
        total = 0
        for chain in config.get("networks", []):
            name, env_name = chain.get("name"), chain.get("rpc_env")
            if name and env_name and os.getenv(env_name):
                lookback = int(chain.get("evm_lookback_blocks", config.get("evm_lookback_blocks", 1900)))
                total += run_evm_once(name, db_path=self.db_path, lookback_blocks=lookback)
        return total

    def solana_listener(self) -> int:
        config = load_solana_config(Path(self.solana_config_path).resolve().parents[1])
        if not os.getenv(config.get("api_key_env", "HELIUS_API_KEY")):
            return 0
        return run_solana_once(db_path=self.db_path, config=config)

    def normalize(self) -> int:
        return len(reconcile_assets(self.db_path))

    def run_cycle(self) -> CycleResult:
        result = CycleResult(started_at=datetime.now(timezone.utc))
        for name, operation in (("cex_refresh", self.cex_refresh),
                                ("tier0_poll", self.tier0_poll),
                                ("evm_listeners", self.evm_listeners),
                                ("solana_listener", self.solana_listener),
                                ("normalization", self.normalize)):
            result.jobs.append(self.run_job(name, operation))
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
