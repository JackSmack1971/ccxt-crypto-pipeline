from datetime import datetime, timedelta
import socket

import pytest

from analysis.backtesting import BacktestConfig, simulate
from analysis.backtesting.simulator import _bar_interval
from analysis.datasets import Asset, Bar, DatasetPolicy, DatasetSnapshot
from analysis.metrics import compute_metrics
from analysis.runs import write_failed_run, write_run
from analysis.strategies import BuyAndHoldStrategy, TargetPosition
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


class _ScriptedStrategy:
    name = "scripted-test"
    version = "1"

    def __init__(self, targets, *, canonical_id=None):
        self.targets = targets
        self.canonical_id = canonical_id

    def on_bar(self, frame):
        quantity = self.targets.get(frame.bar.timestamp)
        if quantity is None:
            return None
        canonical_id = self.canonical_id or frame.bar.canonical_id
        return TargetPosition(canonical_id, quantity)


def _memory_dataset(*, venues=("kraken",), bars_per_asset=3):
    assets = tuple(
        Asset(f"{venue}:AAA/USD", "cex", venue, "AAA/USD", datetime(2025, 1, 1), None)
        for venue in venues
    )
    bars = tuple(
        Bar(asset.canonical_id, datetime(2025, 1, day), 10 * day, 10 * day, 10 * day,
            10 * day, 1, "1d", asset.chain_or_exchange)
        for asset in assets
        for day in range(1, bars_per_asset + 1)
    )
    return DatasetSnapshot(assets, bars, (), (), (), DatasetPolicy(), "fixture")


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("initial_cash", -0.01),
        ("fee_rate", -0.01),
        ("slippage_bps", -0.01),
    ],
)
def test_backtest_config_rejects_negative_cost_and_cash_values(field, value):
    with pytest.raises(ValueError, match="must be non-negative"):
        BacktestConfig(**{field: value}).validate()


@pytest.mark.parametrize(
    "field", ["execution", "missing_bar_policy", "halted_bar_policy", "stale_signal_policy", "source_type"]
)
def test_backtest_config_rejects_unsupported_values(field):
    values = {
        "execution": "close",
        "missing_bar_policy": "execute",
        "halted_bar_policy": "execute",
        "stale_signal_policy": "hold",
        "source_type": "dex",
    }
    expected_messages = {
        "execution": "unsupported execution assumption",
        "missing_bar_policy": "bar policies",
        "halted_bar_policy": "bar policies",
        "stale_signal_policy": "stale_signal_policy",
        "source_type": "unsupported execution universe",
    }
    with pytest.raises(ValueError, match=expected_messages[field]):
        BacktestConfig(**{field: values[field]}).validate()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("initial_cash", 0),
        ("fee_rate", 0),
        ("slippage_bps", 0),
        ("execution", "next_bar_open"),
        ("missing_bar_policy", "skip"),
        ("missing_bar_policy", "error"),
        ("halted_bar_policy", "skip"),
        ("halted_bar_policy", "error"),
        ("stale_signal_policy", "execute_next_available"),
        ("stale_signal_policy", "skip"),
        ("stale_signal_policy", "error"),
        ("source_type", "cex"),
    ],
)
def test_backtest_config_accepts_documented_values(field, value):
    BacktestConfig(**{field: value}).validate()


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        ("1m", timedelta(minutes=1)),
        ("1h", timedelta(hours=1)),
        ("1d", timedelta(days=1)),
        ("1w", timedelta(weeks=1)),
        ("15m", timedelta(minutes=15)),
        ("12h", timedelta(hours=12)),
        ("365d", timedelta(days=365)),
    ],
)
def test_bar_interval_parses_supported_timeframes(timeframe, expected):
    assert _bar_interval(timeframe) == expected


@pytest.mark.parametrize("timeframe", ["0m", "-1h", "m", "1", "1M", "1x", "abc", "1.5h", ""])
def test_bar_interval_rejects_unsupported_timeframes(timeframe):
    with pytest.raises(ValueError, match="unsupported timeframe for gap detection"):
        _bar_interval(timeframe)


def test_empty_dataset_is_rejected_before_simulation():
    dataset = _memory_dataset(bars_per_asset=0)
    with pytest.raises(ValueError, match="insufficient bars: dataset contains no eligible bars"):
        simulate(dataset, BuyAndHoldStrategy())


def test_execution_rejects_cross_venue_and_explicit_venue_mismatch():
    cross_venue = _memory_dataset(venues=("kraken", "coinbase"), bars_per_asset=1)
    with pytest.raises(ValueError, match="cross-venue execution is unsupported"):
        simulate(cross_venue, BuyAndHoldStrategy())
    with pytest.raises(ValueError, match="outside configured venue 'coinbase'"):
        simulate(_memory_dataset(bars_per_asset=1), BuyAndHoldStrategy(), BacktestConfig(venue="coinbase"))


def test_buy_and_sell_ledger_records_transitions_and_cash_accounting():
    t1, t2, t3 = (datetime(2025, 1, day) for day in (1, 2, 3))
    strategy = _ScriptedStrategy({t1: 1, t2: 0, t3: 0})
    result = simulate(_memory_dataset(), strategy, BacktestConfig(fee_rate=0, slippage_bps=0))

    assert [(trade["side"], trade["quantity"], trade["price"], trade["signal_time"], trade["timestamp"])
            for trade in result.trades] == [
        ("buy", 1, 20, "2025-01-01T00:00:00", "2025-01-02T00:00:00"),
        ("sell", 1, 30, "2025-01-02T00:00:00", "2025-01-03T00:00:00"),
    ]
    assert [order["status"] for order in result.orders[:2]] == ["filled", "filled"]
    assert result.trades[0]["cash_after"] == 9_980
    assert result.trades[1]["cash_after"] == 10_010
    assert result.equity[-1]["cash"] == 10_010
    assert result.equity[-1]["positions"] == {"kraken:AAA/USD": 0.0}


@pytest.mark.parametrize("quantity", [-1, float("nan"), float("inf")])
def test_strategy_rejects_invalid_or_short_target(quantity):
    t1 = datetime(2025, 1, 1)
    strategy = _ScriptedStrategy({t1: quantity})
    with pytest.raises(ValueError, match="short positions are unsupported"):
        simulate(_memory_dataset(bars_per_asset=1), strategy)


def test_insufficient_cash_is_recorded_as_rejected_order():
    t1 = datetime(2025, 1, 1)
    result = simulate(_memory_dataset(bars_per_asset=2), _ScriptedStrategy({t1: 2}),
                      BacktestConfig(initial_cash=1, fee_rate=0, slippage_bps=0))
    assert result.trades == ()
    assert result.orders[0] == {
        "canonical_id": "kraken:AAA/USD",
        "signal_time": "2025-01-01T00:00:00",
        "execution_time": "2025-01-02T00:00:00",
        "status": "rejected_insufficient_cash",
        "requested_quantity": 2,
    }


@pytest.mark.parametrize("policy", ["execute_next_available", "skip"])
def test_stale_signal_policy_controls_gap_execution(policy, tmp_path):
    db = _fixture(tmp_path / policy)
    conn = connect(db)
    conn.execute("DELETE FROM ohlcv WHERE timestamp = '2025-01-02'")
    conn.close()
    result = simulate(DatasetSnapshot.from_duckdb(db), BuyAndHoldStrategy(),
                      BacktestConfig(stale_signal_policy=policy))
    if policy == "execute_next_available":
        assert result.trades[0]["timestamp"] == "2025-01-03T00:00:00"
    else:
        assert any(order["status"] == "skipped_stale_signal" for order in result.orders)


def test_stale_signal_error_policy_rejects_gap_execution(tmp_path):
    db = _fixture(tmp_path / "stale-error")
    conn = connect(db)
    conn.execute("DELETE FROM ohlcv WHERE timestamp = '2025-01-02'")
    conn.close()
    with pytest.raises(ValueError, match="stale signal"):
        simulate(DatasetSnapshot.from_duckdb(db), BuyAndHoldStrategy(),
                 BacktestConfig(stale_signal_policy="error"))


def test_final_pending_order_is_explicitly_skipped():
    result = simulate(_memory_dataset(bars_per_asset=1), BuyAndHoldStrategy())
    assert result.trades == ()
    assert result.orders[-1] == {
        "canonical_id": "kraken:AAA/USD",
        "signal_time": "2025-01-01T00:00:00",
        "status": "skipped_insufficient_bar",
    }


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


def test_equity_is_one_state_per_timestamp_for_multiple_assets():
    assets = (
        Asset("kraken:AAA/USD", "cex", "kraken", "AAA/USD", datetime(2025, 1, 1), None),
        Asset("kraken:BBB/USD", "cex", "kraken", "BBB/USD", datetime(2025, 1, 1), None),
    )
    bars = tuple(Bar(asset.canonical_id, timestamp, 10, 10, 10, close, 1, "1d", "kraken")
                 for timestamp, close in ((datetime(2025, 1, 1), 10), (datetime(2025, 1, 2), 11))
                 for asset in assets)
    result = simulate(DatasetSnapshot(assets, bars, (), (), (), DatasetPolicy(), "fixture"), BuyAndHoldStrategy())
    assert [row["timestamp"] for row in result.equity] == ["2025-01-01T00:00:00", "2025-01-02T00:00:00"]


@pytest.mark.parametrize(("frequency", "periods"), [("1h", 8760), ("1d", 365)])
def test_metrics_annualize_from_declared_frequency(frequency, periods):
    equity = [{"timestamp": "2025-01-01T00:00:00", "equity": 100},
              {"timestamp": "2025-01-01T01:00:00" if frequency == "1h" else "2025-01-02T00:00:00", "equity": 101},
              {"timestamp": "2025-01-01T02:00:00" if frequency == "1h" else "2025-01-03T00:00:00", "equity": 100}]
    assert compute_metrics(equity, observation_frequency=frequency)["annualization_periods"] == periods


def test_metrics_report_irregular_timestamp_spacing():
    equity = [{"timestamp": "2025-01-01T00:00:00", "equity": 100},
              {"timestamp": "2025-01-01T01:00:00", "equity": 101},
              {"timestamp": "2025-01-01T03:00:00", "equity": 100}]
    metrics = compute_metrics(equity)
    assert metrics["irregular_intervals"] is True
    assert metrics["observation_interval_seconds"] == pytest.approx(5400)


def test_stale_signal_policy_is_explicit_for_missing_gap(tmp_path):
    db = _fixture(tmp_path / "stale")
    conn = connect(db)
    conn.execute("DELETE FROM ohlcv WHERE timestamp = '2025-01-02'")
    conn.close()
    dataset = DatasetSnapshot.from_duckdb(db)
    result = simulate(dataset, BuyAndHoldStrategy(), BacktestConfig(stale_signal_policy="skip"))
    assert any(order["status"] == "skipped_stale_signal" for order in result.orders)


def test_halted_bar_does_not_make_signal_stale(tmp_path):
    db = _fixture(tmp_path / "halted")
    conn = connect(db)
    conn.execute("DELETE FROM ohlcv WHERE timestamp = '2025-01-02'")
    conn.execute("INSERT INTO ohlcv VALUES ('kraken:AAA/USD', '2025-01-02', 0, 0, 0, 0, 0, '1d', 'kraken')")
    conn.close()
    dataset = DatasetSnapshot.from_duckdb(db)
    result = simulate(dataset, BuyAndHoldStrategy(), BacktestConfig(stale_signal_policy="skip"))
    assert result.trades[0]["timestamp"] == "2025-01-03T00:00:00"
    assert not any(order["status"] == "skipped_stale_signal" for order in result.orders)


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
