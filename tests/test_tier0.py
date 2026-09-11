from datetime import datetime, timezone

from ingestion.dex.tier0.clients import normalize_pool
from ingestion.dex.tier0.poller import poll_network
from storage.db import read_asset_relationships, read_assets, read_events


def test_normalize_pool_and_poll_writes_canonical_rows(tmp_path):
    pool = {"id": "ethereum_pool1", "attributes": {"address": "0xpool", "pool_created_at": "2025-01-01T00:00:00Z"},
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
