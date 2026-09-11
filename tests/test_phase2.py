from datetime import datetime
import socket

import pytest

from analysis.backtesting import BacktestConfig, simulate
from analysis.datasets import Asset, Bar, DatasetPolicy, DatasetSnapshot
from analysis.metrics import compute_metrics
from analysis.runs import write_failed_run, write_run
from analysis.strategies import BuyAndHoldStrategy
from storage.db import connect, insert_event, insert_ohlcv_batch, read_ohlcv, upsert_asset, upsert_metadata


def _fixture(tmp_path, *, future_metadata=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    db = tmp_path / "fixture.duckdb"
    conn = connect(db)
    upsert_asset({"canonical_id": "kraken:AAA/USD", "source_type": "cex", "chain_or_exchange": "kraken",
                  "symbol_or_contract": "AAA/USD", "first_seen": datetime(2025, 1, 1)}, connection=conn)
    insert_ohlcv_batch([
        {"canonical_id": "kraken:AAA/USD", "timestamp": datetime(2025, 1, 1), "open": 10, "high": 11,
         "low": 9, "close": 10, "volume": 1, "timeframe": "1d", "source": "kraken"},
        {"canonical_id": "kraken:AAA/USD", "timestamp": datetime(2025, 1, 2), "open": 20, "high": 21,
         "low": 19, "close": 20, "volume": 1, "timeframe": "1d", "source": "kraken"},
        {"canonical_id": "kraken:AAA/USD", "timestamp": datetime(2025, 1, 3), "open": 30, "high": 31,
         "low": 29, "close": 30, "volume": 1, "timeframe": "1d", "source": "kraken"},
    ], connection=conn, parquet_dir=tmp_path / "parquet")
    upsert_metadata({"canonical_id": "kraken:AAA/USD", "last_updated": datetime(2025, 1, 4 if future_metadata else 1)}, connection=conn)
    conn.close()
    return db


def test_point_in_time_metadata_and_next_bar_fee_slippage(tmp_path):
    dataset = DatasetSnapshot.from_duckdb(_fixture(tmp_path, future_metadata=True), DatasetPolicy())
    assert dataset.metadata_at("kraken:AAA/USD", datetime(2025, 1, 2)) is None
    result = simulate(dataset, BuyAndHoldStrategy(1), BacktestConfig(fee_rate=0.01, slippage_bps=100))
    assert result.trades[0]["timestamp"] == "2025-01-02T00:00:00"
    assert result.trades[0]["price"] == pytest.approx(20.2)
    assert result.trades[0]["fee"] == pytest.approx(0.202)
    assert result.trades[0]["slippage"] == pytest.approx(0.2)
    assert result.trades[0]["signal_time"] == "2025-01-01T00:00:00"


def test_replay_artifacts_are_byte_identical(tmp_path):
    dataset = DatasetSnapshot.from_duckdb(_fixture(tmp_path), DatasetPolicy(), tmp_path / "parquet")
    strategy = BuyAndHoldStrategy(1)
    result = simulate(dataset, strategy)
    first = write_run(result, dataset, strategy, tmp_path / "runs")
    second = write_run(result, dataset, strategy, tmp_path / "runs")
    assert first == second
    for artifact in ("manifest.json", "trades.json", "orders.json", "equity.json", "metrics.json"):
        assert (first / artifact).read_bytes() == (second / artifact).read_bytes()
    metrics = compute_metrics(result.equity, trades=result.trades)
    assert metrics["total_return"] == pytest.approx(0.000998)
    assert metrics["total_fees"] == pytest.approx(0.02)


def test_fixture_run_is_network_independent(tmp_path, monkeypatch):
    def deny_network(*_args, **_kwargs):
        raise AssertionError("offline Phase 2 fixture attempted network access")

    with pytest.raises(AssertionError, match="offline Phase 2 fixture attempted network access"):
        deny_network()
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    dataset = DatasetSnapshot.from_duckdb(_fixture(tmp_path), DatasetPolicy(), tmp_path / "parquet")
    result = simulate(dataset, BuyAndHoldStrategy())
    run_dir = write_run(result, dataset, BuyAndHoldStrategy(), tmp_path / "runs")
    assert (run_dir / "manifest.json").exists()


def test_run_manifest_redacts_credential_fields(tmp_path):
    dataset = DatasetSnapshot.from_duckdb(_fixture(tmp_path), DatasetPolicy())
    result = simulate(dataset, BuyAndHoldStrategy(1))
    run_dir = write_run(result, dataset, BuyAndHoldStrategy(1), tmp_path / "runs",
                        strategy_config={"api_key": "do-not-write", "threshold": 1})
    manifest = (run_dir / "manifest.json").read_text()
    assert "do-not-write" not in manifest
    assert "[REDACTED]" in manifest


def test_failed_run_is_recorded_without_result_artifacts(tmp_path):
    run_dir = write_failed_run(tmp_path / "runs", {"rpc_url": "https://secret.example"},
                               ValueError("api_key=do-not-write https://user:pass@leaked.example/rpc"))
    manifest = (run_dir / "manifest.json").read_text()
    assert '"status":"failed"' in manifest
    assert '"error_type":"ValueError"' in manifest
    assert "secret.example" not in manifest
    assert "do-not-write" not in manifest
    assert "user:pass" not in manifest
    assert list(run_dir.iterdir()) == [run_dir / "manifest.json"]


def test_unsupported_execution_is_actionable(tmp_path):
    dataset = DatasetSnapshot.from_duckdb(_fixture(tmp_path))
    with pytest.raises(ValueError, match="unsupported execution assumption"):
        simulate(dataset, BuyAndHoldStrategy(), BacktestConfig(execution="close"))


def test_multi_source_bars_are_preserved_and_unambiguous_selection_is_required(tmp_path):
    db = _fixture(tmp_path)
    conn = connect(db)
    conn.execute("INSERT INTO ohlcv VALUES ('kraken:AAA/USD', '2025-01-1 00:00:00', 10, 11, 9, 10, 1, '1d', 'other')")
    conn.close()
    assert len(read_ohlcv(db)) == 4
    with pytest.raises(ValueError, match="ambiguous bar source"):
        DatasetSnapshot.from_duckdb(db)
    selected = DatasetSnapshot.from_duckdb(db, DatasetPolicy(sources=("kraken",)))
    assert {bar.source for bar in selected.all_bars()} == {"kraken"}


def test_missing_halted_and_insufficient_bars_are_explicit(tmp_path):
    db = _fixture(tmp_path)
    conn = connect(db)
    conn.execute("DELETE FROM ohlcv WHERE timestamp = '2025-01-02'")
    conn.execute("INSERT INTO ohlcv VALUES ('kraken:AAA/USD', '2025-01-02', 0, 0, 0, 0, 0, '1d', 'kraken')")
    conn.close()
    dataset = DatasetSnapshot.from_duckdb(db)
    result = simulate(dataset, BuyAndHoldStrategy(), BacktestConfig())
    assert any(order["status"] == "skipped_halted" for order in result.orders)
    assert any(order["status"] == "skipped_insufficient_bar" for order in result.orders)
    assert result.trades[0]["timestamp"] == "2025-01-03T00:00:00"
    with pytest.raises(ValueError, match="halted bar"):
        simulate(dataset, BuyAndHoldStrategy(), BacktestConfig(halted_bar_policy="error"))

    gap_db = _fixture(tmp_path / "gap")
    gap_conn = connect(gap_db)
    gap_conn.execute("DELETE FROM ohlcv WHERE timestamp = '2025-01-02'")
    gap_conn.close()
    gap_dataset = DatasetSnapshot.from_duckdb(gap_db)
    with pytest.raises(ValueError, match="missing bar"):
        simulate(gap_dataset, BuyAndHoldStrategy(), BacktestConfig(missing_bar_policy="error"))

    short_db = tmp_path / "short.duckdb"
    short_conn = connect(short_db)
    upsert_asset({"canonical_id": "kraken:AAA/USD", "source_type": "cex", "chain_or_exchange": "kraken",
                  "symbol_or_contract": "AAA/USD", "first_seen": datetime(2025, 1, 1)}, connection=short_conn)
    insert_ohlcv_batch([{"canonical_id": "kraken:AAA/USD", "timestamp": datetime(2025, 1, 1), "open": 10,
                         "high": 10, "low": 10, "close": 10, "volume": 1, "timeframe": "1d", "source": "kraken"}],
                       connection=short_conn)
    short_conn.close()
    with pytest.raises(ValueError, match="insufficient bars"):
        simulate(DatasetSnapshot.from_duckdb(short_db), BuyAndHoldStrategy(), BacktestConfig(missing_bar_policy="error"))


def test_unknown_identity_is_rejected(tmp_path):
    db = _fixture(tmp_path)
    conn = connect(db)
    insert_event({"canonical_id": "kraken:UNKNOWN", "event_type": "new", "timestamp": datetime(2025, 1, 1),
                  "payload_json": {}, "source": "fixture"}, connection=conn)
    conn.close()
    with pytest.raises(ValueError, match="unknown canonical asset identities"):
        DatasetSnapshot.from_duckdb(db)


def test_non_positive_execution_price_is_rejected():
    asset = Asset("kraken:AAA/USD", "cex", "kraken", "AAA/USD", datetime(2025, 1, 1), None)
    bars = (
        Bar("kraken:AAA/USD", datetime(2025, 1, 1), 10, 10, 10, 10, 1, "1d", "kraken"),
        Bar("kraken:AAA/USD", datetime(2025, 1, 2), 0, 1, 1, 1, 1, "1d", "kraken"),
    )
    dataset = DatasetSnapshot((asset,), bars, (), (), (), DatasetPolicy(), "fixture")
    with pytest.raises(ValueError, match="non-positive price"):
        simulate(dataset, BuyAndHoldStrategy(), BacktestConfig())


def test_parquet_failure_rolls_back_ohlcv_write(tmp_path):
    db = _fixture(tmp_path)
    bad_path = tmp_path / "not-a-directory"
    bad_path.write_text("not a directory")
    conn = connect(db)
    try:
        with pytest.raises(Exception):
            insert_ohlcv_batch([{"canonical_id": "kraken:AAA/USD", "timestamp": datetime(2025, 1, 4),
                                 "open": 40, "high": 40, "low": 40, "close": 40, "volume": 1,
                                 "timeframe": "1d", "source": "kraken"}],
                               connection=conn, parquet_dir=bad_path)
    finally:
        conn.close()
    check = connect(db)
    assert check.execute("SELECT COUNT(*) FROM ohlcv WHERE timestamp = '2025-01-04'").fetchone()[0] == 0
    check.close()
