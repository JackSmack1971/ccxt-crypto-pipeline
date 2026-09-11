import json
from datetime import datetime, timezone

from ingestion.solana.helius import HeliusClient
from ingestion.solana.listener import extract_mints, extract_pool_addresses, is_solana_address, run_once
from storage.db import read_asset_relationships, read_assets, read_events, read_metadata, read_runs


class Response:
    def __init__(self, body, status_code=200):
        self.body, self.status_code = body, status_code
        self.headers = {}

    def json(self): return self.body
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)


class Session:
    def __init__(self, responses): self.responses = iter(responses)
    def request(self, *args, **kwargs): return next(self.responses)


def test_extract_mints_from_mint_and_pool_shapes():
    mint_a = "So11111111111111111111111111111111111111112"
    mint_b = "11111111111111111111111111111111"
    assert extract_mints({"events": {"tokenMint": mint_a, "token1Mint": mint_b}}) == [mint_a, mint_b]
    assert not is_solana_address("not-a-mint")


def test_helius_client_normalizes_das_and_largest_accounts(monkeypatch):
    monkeypatch.setenv("HELIUS_API_KEY", "test-key")
    session = Session([Response([{"type": "TOKEN_MINT", "mint": "MintA"}]),
                       Response({"result": {"content": {"metadata": {"name": "Test"}}}}),
                       Response({"result": {"value": [{"address": "holder"}]}})])
    client = HeliusClient({"enhanced_base_url": "https://enhanced", "das_url": "https://das",
                           "rpc_url": "https://rpc", "max_requests_per_second": 1000}, session)
    assert client.recent_transactions("program")
    assert client.get_asset("MintA")["content"]["metadata"]["name"] == "Test"
    assert len(client.largest_accounts("MintA")) == 1


def test_run_once_persists_comparable_solana_event_and_metadata(tmp_path):
    mint = "So11111111111111111111111111111111111111112"

    class Client:
        def recent_transactions(self, address, *, limit):
            return [{"type": "TOKEN_MINT", "signature": "sig", "timestamp": 1735787040,
                     "feePayer": "deployer", "events": {"tokenMint": mint}}]
        def get_asset(self, address):
            return {"content": {"metadata": {"name": "Fixture", "symbol": "FIX"}},
                    "token_info": {"decimals": 9, "supply": 100}}
        def largest_accounts(self, address): return [{"address": "holder"}]

    cfg = {"programs": {"token_metadata": "metadata-program"},
           "discovery": {"limit": 1, "transaction_types": ["TOKEN_MINT"]}}
    db = str(tmp_path / "solana.duckdb")
    assert run_once(db_path=db, config=cfg, client=Client()) == 1
    assert read_assets(db)[0]["canonical_id"] == f"solana:{mint}"
    assert read_events(db)[0]["event_type"] == "token_mint_detected"
    metadata = read_metadata(db)[0]
    assert metadata["holder_count"] == 1
    assert json.loads(metadata["risk_flags_json"])["token_metadata"]["symbol"] == "FIX"
    assert read_runs(db)[0]["status"] == "success"


def test_create_pool_persists_market_and_address_scoped_constituents(tmp_path):
    pool = "11111111111111111111111111111111"
    mint_a = "So11111111111111111111111111111111111111112"
    mint_b = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    transaction = {"type": "CREATE_POOL", "timestamp": 1735787040, "feePayer": "deployer",
                   "events": {"poolAddress": pool, "token1Mint": mint_a, "token2Mint": mint_b}}

    class Client:
        def recent_transactions(self, address, *, limit): return [transaction]
        def get(self, address): return None
        def get_asset(self, address): return {}
        def largest_accounts(self, address): return []

    assert extract_pool_addresses(transaction) == [pool]
    db = str(tmp_path / "solana-pool.duckdb")
    cfg = {"programs": {"orca": "program"},
           "discovery": {"limit": 1, "transaction_types": ["CREATE_POOL"]}}
    assert run_once(db_path=db, config=cfg, client=Client()) == 2
    assert read_events(db)[0]["canonical_id"] == f"solana:{pool}"
    relationships = read_asset_relationships(db)
    assert {(row["relationship_type"], row["asset_canonical_id"]) for row in relationships} == {
        ("constituent_0", f"solana:{mint_a}"), ("constituent_1", f"solana:{mint_b}")}


def test_config_includes_required_solana_venues():
    from ingestion.solana.config import load_config
    programs = load_config()["programs"]
    assert {"orca_whirlpools", "pump_fun", "pump_swap"}.issubset(programs)
