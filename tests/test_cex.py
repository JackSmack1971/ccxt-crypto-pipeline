from datetime import datetime, timezone

from ingestion.cex import backfill, universe
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
