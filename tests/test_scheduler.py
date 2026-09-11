from scheduler.pipeline import Pipeline, build_scheduler
from datetime import datetime

from storage.db import log_run_end, log_run_start, read_runs
from scheduler.status import health_report


def test_cycle_runs_all_stages_and_records_structured_results(tmp_path):
    pipeline = Pipeline(db_path=str(tmp_path / "pipeline.duckdb"))
    calls = []
    for name in ("cex_refresh", "tier0_poll", "evm_listeners", "solana_listener", "normalize"):
        setattr(pipeline, name, lambda name=name: calls.append(name) or 1)

    result = pipeline.run_cycle()

    assert result.success
    assert calls == ["cex_refresh", "tier0_poll", "evm_listeners", "solana_listener", "normalize"]
    assert [job.status for job in result.jobs] == ["success"] * 5
    runs = read_runs(pipeline.db_path)
    assert {run["job_name"] for run in runs} == {
        "scheduler:cex_refresh", "scheduler:tier0_poll", "scheduler:evm_listeners",
        "scheduler:solana_listener", "scheduler:normalization",
    }
    assert all(run["finished_at"] is not None for run in runs)


def test_cycle_isolates_job_failure_and_continues(tmp_path):
    pipeline = Pipeline(db_path=str(tmp_path / "pipeline.duckdb"))
    calls = []

    def fail():
        calls.append("failed")
        raise RuntimeError("fixture failure")

    pipeline.cex_refresh = fail
    pipeline.tier0_poll = lambda: calls.append("tier0") or 2
    pipeline.evm_listeners = lambda: 0
    pipeline.solana_listener = lambda: 0
    pipeline.normalize = lambda: 0
    result = pipeline.run_cycle()

    assert not result.success
    assert result.jobs[0].status == "failed"
    assert calls == ["failed", "tier0"]
    assert any(run["status"] == "failed" and run["error_message"] == "fixture failure"
               for run in read_runs(pipeline.db_path))
    assert any(run["job_name"] == "scheduler:tier0_poll" and run["status"] == "success"
               for run in read_runs(pipeline.db_path))


def test_scheduler_has_required_cadences(tmp_path):
    scheduler = build_scheduler(Pipeline(db_path=str(tmp_path / "pipeline.duckdb")))
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"cex_refresh", "tier0_poll", "evm_listeners", "solana_listener", "normalization"}
    assert jobs["cex_refresh"].trigger.interval.days == 1
    assert jobs["tier0_poll"].trigger.interval.total_seconds() == 20 * 60
    assert jobs["evm_listeners"].trigger.interval.total_seconds() == 60
    assert jobs["solana_listener"].trigger.interval.total_seconds() == 60


def test_solana_listener_without_credentials_is_a_safe_noop(tmp_path, monkeypatch):
    monkeypatch.delenv("HELIUS_API_KEY", raising=False)
    pipeline = Pipeline(db_path=str(tmp_path / "pipeline.duckdb"))
    assert pipeline.solana_listener() == 0


def test_evm_listener_uses_configured_lookback(tmp_path, monkeypatch):
    monkeypatch.setenv("EVM_RPC_URL_BASE", "https://rpc.example")
    pipeline = Pipeline(db_path=str(tmp_path / "pipeline.duckdb"))
    monkeypatch.setattr("scheduler.pipeline.load_chain_config", lambda _: {
        "networks": [{"name": "base", "rpc_env": "EVM_RPC_URL_BASE", "evm_lookback_blocks": 17}]
    })
    observed = []
    monkeypatch.setattr("scheduler.pipeline.run_evm_once",
                        lambda name, **kwargs: observed.append((name, kwargs)) or 0)
    assert pipeline.evm_listeners() == 0
    assert observed == [("base", {"db_path": pipeline.db_path, "lookback_blocks": 17})]


def test_health_report_uses_deterministic_tie_breaking(tmp_path):
    db = str(tmp_path / "pipeline.duckdb")
    started = datetime(2026, 1, 1)
    first = log_run_start("job", db, started_at=started, run_id="a")
    second = log_run_start("job", db, started_at=started, run_id="b")
    log_run_end(first, "success", db, finished_at=started)
    log_run_end(second, "success", db, finished_at=started)

    assert health_report(db)["latest_by_job"]["job"]["run_id"] == "b"
