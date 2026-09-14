from datetime import datetime, timezone

from ingestion.dex.tier0.clients import normalize_pool
from ingestion.dex.tier0.poller import poll_network
from storage.db import (read_asset_relationships, read_assets, read_dex_price_observations,
                        read_events, read_observation_capabilities, read_price_observations)


def test_normalize_pool_and_poll_writes_canonical_rows(tmp_path):
    pool = {"id": "ethereum_pool1", "attributes": {"address": "0xpool", "pool_created_at": "2025-01-01T00:00:00Z",
             "base_token_price_usd": "1.25", "quote_token_price_usd": "1.00", "reserve_in_usd": "12000",
             "volume_usd": {"h24": "500"}},
            "relationships": {"base_token": {"data": {"id": "ethereum_0xbase"}},
                               "quote_token": {"data": {"id": "ethereum_0xquote"}}}}

    class FakeGecko:
        def new_pools(self, network):
            return [normalize_pool(pool, network)]
        def trending_pools(self, network):
            return []

    db = str(tmp_path / "pipeline.duckdb")
    poll_network({"name": "ethereum", "gecko_network": "ethereum"}, db_path=db,
                 gecko=FakeGecko(), now=datetime(2025, 1, 2, tzinfo=timezone.utc))
    poll_network({"name": "ethereum", "gecko_network": "ethereum"}, db_path=db,
                 gecko=FakeGecko(), now=datetime(2025, 1, 2, tzinfo=timezone.utc))
    assert len(read_events(db)) == 1
    assert read_events(db)[0]["canonical_id"] == "ethereum:0xpool"
    assert {row["canonical_id"] for row in read_assets(db)} == {
        "ethereum:0xpool", "ethereum:0xbase", "ethereum:0xquote"
    }
    assert [(row["relationship_type"], row["asset_canonical_id"])
            for row in read_asset_relationships(db)] == [
                ("base", "ethereum:0xbase"), ("quote", "ethereum:0xquote")]
    observations = read_price_observations(db)
    assert len(observations) == 2
    assert {(row["asset_canonical_id"], row["price"], row["liquidity_usd"], row["volume_usd"])
            for row in observations} == {("ethereum:0xbase", 1.25, 12000.0, 500.0),
                                         ("ethereum:0xquote", 1.0, 12000.0, 500.0)}


def test_evm_and_solana_price_fixtures_persist_actual_candles_and_capability(tmp_path):
    created = datetime(2025, 1, 1, tzinfo=timezone.utc)

    class FakeGecko:
        def new_pools(self, network):
            return [{"pool_address": f"{network}-pool", "created_at": created,
                     "base_token_address": f"{network}-base", "quote_token_address": f"{network}-quote",
                     "dex_id": "fixture-dex", "reserve_usd": 12000}]
        def trending_pools(self, network): return []
        def pool_ohlcv(self, network, address, **kwargs):
            # The missing 00:01 candle deliberately proves gaps remain gaps.
            return [{"timestamp": created, "open": 1, "high": 2, "low": .5, "close": 1.5, "volume": 10},
                    {"timestamp": created.replace(minute=2), "open": 1.5, "high": 2, "low": 1, "close": 2, "volume": 12}]

    db = str(tmp_path / "prices.duckdb")
    for chain in ("ethereum", "solana"):
        poll_network({"name": chain, "gecko_network": chain}, db_path=db, gecko=FakeGecko(),
                     now=created, price_config={"enabled": True, "timeframe": "minute", "aggregate": 1})
    rows = read_dex_price_observations(db)
    assert {(row["asset_canonical_id"].split(":", 1)[0], row["timestamp"].minute) for row in rows} == {
        ("ethereum", 0), ("ethereum", 2), ("solana", 0), ("solana", 2)}
    assert all(row["quote_asset_canonical_id"].endswith("-quote") for row in rows)
    assert {(row["chain"], row["status"]) for row in read_observation_capabilities(db)} == {
        ("ethereum", "AVAILABLE"), ("solana", "AVAILABLE")}


def test_solana_shaped_network_persists_the_same_observation_contract(tmp_path):
    pool = {"id": "solana_pool1", "attributes": {"address": "pool", "pool_created_at": "2025-01-01T00:00:00Z",
             "base_token_price_usd": "2.5", "reserve_in_usd": "8000"},
            "relationships": {"base_token": {"data": {"id": "solana_base"}}}}

    class FakeGecko:
        def new_pools(self, network):
            return [normalize_pool(pool, network)]
        def trending_pools(self, network):
            return []

    db = str(tmp_path / "solana.duckdb")
    poll_network({"name": "solana", "gecko_network": "solana"}, db_path=db,
                 gecko=FakeGecko(), now=datetime(2025, 1, 2, tzinfo=timezone.utc))
    observations = read_price_observations(db)
    assert [(row["asset_canonical_id"], row["market_canonical_id"], row["price"], row["cadence"])
            for row in observations] == [("solana:base", "solana:pool", 2.5, "20m")]
