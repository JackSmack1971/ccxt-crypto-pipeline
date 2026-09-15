from datetime import datetime, timezone
import sys

import pytest

from ingestion.cex import backfill, refresh, universe
from ingestion.cex import common
from ingestion.cex.common import contract_address
from storage.db import insert_ohlcv_batch, read_ohlcv, read_runs, upsert_asset


class FakeExchange:
    def __init__(self):
        self.markets = {"BTC/USDT": {"symbol": "BTC/USDT", "spot": True}}
        self.ohlcv_calls = []
        self.closed = False

    def fetch_markets(self):
        return list(self.markets.values())

    def load_markets(self):
        return self.markets

    def fetch_tickers(self):
        return {"BTC/USDT": {"quoteVolume": 1000}}

    def parse_timeframe(self, timeframe):
        assert timeframe == "1d"
        return 86400

    def fetch_ohlcv(self, symbol, timeframe, since, limit=720):
        self.ohlcv_calls.append(since)
        first = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        if since <= first:
            return [[first, 1, 2, 0.5, 1.5, 10]]
        return []

    def close(self):
        self.closed = True


class RefreshExchange:
    def __init__(self, *, fail_tickers=False):
        self.ticker_calls = 0
        self.ohlcv_calls = []
        self.closed = False
        self.fail_tickers = fail_tickers

    def fetch_tickers(self):
        self.ticker_calls += 1
        if self.fail_tickers:
            raise RuntimeError("ticker failure")
        return {"BTC/USDT": {"quoteVolume": 1000}}

    def parse_timeframe(self, timeframe):
        assert timeframe == "1d"
        return 86400

    def fetch_ohlcv(self, symbol, timeframe, since, limit=720):
        self.ohlcv_calls.append((symbol, timeframe, since, limit))
        return [[1735776000000, 1, 2, 0.5, 1.5, 10], [1735862400000, 1]]

    def close(self):
        self.closed = True


class BackfillFilteringExchange(FakeExchange):
    def __init__(self):
        super().__init__()
        self.closed = False

    def fetch_ohlcv(self, symbol, timeframe, since, limit=720):
        self.ohlcv_calls.append(since)
        first = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        return [[first, 1, 2, 0.5, 1.5, 10], [first + 86400000, 1]]

    def close(self):
        self.closed = True


def test_backfill_is_resumable_and_replay_has_no_duplicate_rows(tmp_path, monkeypatch):
    fake = FakeExchange()
    monkeypatch.setattr(backfill, "create_exchange", lambda exchange_id: fake)
    config = {"max_retries": 0, "backoff_seconds": 0, "ohlcv_limit": 720}
    db_path = str(tmp_path / "pipeline.duckdb")
    parquet_path = str(tmp_path / "parquet")

    backfill.backfill_symbol("kraken", "BTC/USDT", "1d", 1735689600000,
                             config=config, db_path=db_path, parquet_path=parquet_path)
    backfill.backfill_symbol("kraken", "BTC/USDT", "1d", 1735689600000,
                             config=config, db_path=db_path, parquet_path=parquet_path)

    assert len(read_ohlcv(db_path)) == 1
    assert [run["status"] for run in read_runs(db_path)] == ["success", "success"]
    checkpoint = read_ohlcv(db_path)[0]["timestamp"]
    expected_resume = int(checkpoint.replace(tzinfo=timezone.utc).timestamp() * 1000) + 86400000
    assert fake.ohlcv_calls[1] == expected_resume


def test_backfill_filters_short_candles_and_closes_exchange(tmp_path, monkeypatch):
    fake = BackfillFilteringExchange()
    monkeypatch.setattr(backfill, "create_exchange", lambda exchange_id: fake)
    db_path = str(tmp_path / "pipeline.duckdb")

    assert backfill.backfill_symbol(
        "kraken", "BTC/USDT", "1d", 1735689600000,
        config={"max_retries": 0, "backoff_seconds": 0, "ohlcv_limit": 720},
        db_path=db_path,
    ) == 1

    assert len(read_ohlcv(db_path)) == 1
    assert fake.closed
    assert read_runs(db_path)[0]["status"] == "success"


def test_refresh_requests_one_ticker_snapshot_filters_short_candles_and_resumes(tmp_path, monkeypatch):
    fake = RefreshExchange()
    monkeypatch.setattr(refresh, "create_exchange", lambda exchange_id: fake)
    db_path = str(tmp_path / "pipeline.duckdb")
    upsert_asset({"canonical_id": "kraken:BTC/USDT", "source_type": "cex",
                  "chain_or_exchange": "kraken", "symbol_or_contract": "BTC/USDT",
                  "first_seen": datetime(2025, 1, 1)}, db_path)
    insert_ohlcv_batch([{"canonical_id": "kraken:BTC/USDT",
                         "timestamp": datetime(2025, 1, 1), "open": 1, "high": 2,
                         "low": 0.5, "close": 1.5, "volume": 10, "timeframe": "1d",
                         "source": "kraken"}], db_path)

    assert refresh.refresh_exchange(
        "kraken", config={"timeframes": ["1d"], "max_retries": 0, "backoff_seconds": 0},
        db_path=db_path,
    ) == 1

    assert fake.ticker_calls == 1
    assert fake.ohlcv_calls == [("BTC/USDT", "1d", 1735776000000, 720)]
    assert len(read_ohlcv(db_path)) == 2
    assert fake.closed
    assert read_runs(db_path)[0]["status"] == "success"


def test_refresh_logs_failure_propagates_and_closes_exchange(tmp_path, monkeypatch):
    fake = RefreshExchange(fail_tickers=True)
    monkeypatch.setattr(refresh, "create_exchange", lambda exchange_id: fake)
    db_path = str(tmp_path / "pipeline.duckdb")

    with pytest.raises(RuntimeError, match="ticker failure"):
        refresh.refresh_exchange("kraken", config={}, db_path=db_path)

    run = read_runs(db_path)[0]
    assert run["status"] == "failed"
    assert run["error_message"] == "ticker failure"
    assert fake.closed


def test_universe_filters_spot_markets_by_quote_volume(tmp_path, monkeypatch):
    fake = FakeExchange()
    fake.markets["ETH/USDT"] = {"symbol": "ETH/USDT", "spot": True}
    fake.fetch_tickers = lambda: {"BTC/USDT": {"quoteVolume": 1000}, "ETH/USDT": {"quoteVolume": 1}}
    monkeypatch.setattr(universe, "create_exchange", lambda exchange_id: fake)

    assets = universe.discover_universe(
        {"exchanges": ["kraken"], "minimum_24h_quote_volume": 100},
        db_path=str(tmp_path / "pipeline.duckdb"),
    )

    assert [asset["canonical_id"] for asset in assets] == ["kraken:BTC/USDT"]
    assert fake.closed


def test_refresh_main_passes_configured_exchange_and_cli_database_path(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(refresh, "load_config", lambda path: {"exchanges": ["kraken"]})
    monkeypatch.setattr(refresh, "refresh_exchange",
                        lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["refresh", "--config", "custom.yaml", "--db-path",
                                       str(tmp_path / "refresh.duckdb")])

    refresh.main()

    assert calls == [(('kraken',), {'config': {'exchanges': ['kraken']},
                                    'db_path': str(tmp_path / 'refresh.duckdb')})]


def test_universe_main_uses_configured_database_path(monkeypatch):
    calls = []
    config = {"exchanges": ["kraken"], "database_path": "config.duckdb"}
    monkeypatch.setattr(universe, "load_config", lambda path: config)
    monkeypatch.setattr(universe, "discover_universe",
                        lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["universe", "--config", "custom.yaml"])

    universe.main()

    assert calls == [((config,), {"db_path": "config.duckdb"})]


def test_cli_main_uses_cli_database_path_and_configured_parquet_path(monkeypatch, tmp_path):
    calls = []
    config = {"database_path": "config.duckdb", "parquet_path": "config-parquet",
              "exchanges": ["kraken"], "symbol": "BTC/USDT", "timeframe": "1d"}
    monkeypatch.setattr(backfill, "load_config", lambda path: config)
    monkeypatch.setattr(backfill, "backfill_symbol",
                        lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["backfill", "--exchange", "kraken",
                                       "--symbol", "BTC/USDT", "--timeframe", "1d",
                                       "--since", "2025-01-01", "--config", "custom.yaml",
                                       "--db-path", str(tmp_path / "cli.duckdb")])

    backfill.main()

    assert calls[0][0][-1] == int(datetime(2025, 1, 1).timestamp() * 1000)
    assert calls[0][1]["db_path"] == str(tmp_path / "cli.duckdb")
    assert calls[0][1]["parquet_path"] == "config-parquet"


def test_contract_address_reads_exchange_raw_metadata():
    assert contract_address({"info": {"baseAsset": {"contractAddress": "0xUSDC"}}}) == "0xUSDC"


@pytest.mark.parametrize(
    ("contents", "expected"),
    [("database_path: data.duckdb\n", {"database_path": "data.duckdb"}),
     ("", {})],
)
def test_load_config_accepts_mapping_and_empty_yaml(tmp_path, contents, expected):
    path = tmp_path / "cex.yaml"
    path.write_text(contents, encoding="utf-8")

    assert common.load_config(path) == expected


def test_load_config_rejects_non_mapping_yaml(tmp_path):
    path = tmp_path / "cex.yaml"
    path.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a mapping"):
        common.load_config(path)


def test_create_exchange_rejects_unsupported_id():
    with pytest.raises(ValueError, match="unsupported ccxt exchange: missing_exchange"):
        common.create_exchange("missing_exchange")


def test_create_exchange_enables_rate_limit(monkeypatch):
    received = []

    class FakeExchange:
        def __init__(self, options):
            received.append(options)

    monkeypatch.setattr(common.ccxt, "fake_exchange", FakeExchange, raising=False)

    common.create_exchange("fake_exchange")

    assert received == [{"enableRateLimit": True}]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2025-01-01", int(datetime(2025, 1, 1).timestamp() * 1000)),
     ("2025-01-01T00:00:00+00:00", 1735689600000),
     ("2024-12-31T19:00:00-05:00", 1735689600000)],
)
def test_parse_since_converts_iso_values_to_utc_milliseconds(value, expected):
    assert backfill._parse_since(value) == expected


@pytest.mark.parametrize("value", ["1735689600", "not-a-date", ""])
def test_parse_since_rejects_epoch_like_and_malformed_values(value):
    with pytest.raises((TypeError, ValueError)):
        backfill._parse_since(value)
