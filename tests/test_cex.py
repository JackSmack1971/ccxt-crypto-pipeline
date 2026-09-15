from datetime import datetime, timezone

import pytest

from ingestion.cex import backfill, universe
from ingestion.cex import common
from ingestion.cex.common import contract_address
from storage.db import read_ohlcv, read_runs


class FakeExchange:
    def __init__(self):
        self.markets = {"BTC/USDT": {"symbol": "BTC/USDT", "spot": True}}
        self.ohlcv_calls = []

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
        pass


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
    assert fake.ohlcv_calls[1] > fake.ohlcv_calls[0]


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
