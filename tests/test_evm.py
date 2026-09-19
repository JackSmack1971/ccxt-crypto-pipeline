import json
from datetime import datetime, timezone

import pytest

from config.env import MissingEnvironmentValueError
from ingestion.evm.config import resolve_chain_rpc_url, resolve_explorer_credential
from ingestion.evm.listener import observe_once, run_once
from ingestion.evm.models import Capability, CapabilityStatus, EnrichmentResult
from ingestion.evm.providers import EtherscanV2Provider, MegaNodeProvider, RoutescanProvider, build_provider
from ingestion.evm.risk import HoneypotRiskProvider
from ingestion.evm.rpc import PAIR_CREATED_TOPIC, decode_created_asset
from storage.db import (get_ingestion_cursor, insert_event, read_event_history, read_events,
                        read_evm_block_observations, read_metadata, read_runs)


def fixture_block(number, suffix="aa", parent_suffix="00"):
    return {"hash": "0x" + suffix * 32, "parentHash": "0x" + parent_suffix * 32,
            "timestamp": "0x" + format(1735689600 + number, "x")}


class Response:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code
    def json(self): return self.body
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)


class Session:
    def __init__(self, responses): self.responses = iter(responses)
    def get(self, *args, **kwargs): return next(self.responses)


def test_provider_routing_and_shared_etherscan_credential(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "shared")
    base = {"providers": {"ethereum": "etherscan_v2", "arbitrum": "etherscan_v2",
                           "base": "routescan", "bsc": "bsctrace_meganode"},
            "etherscan_v2": {"base_url": "https://etherscan.test", "api_key_env": "ETHERSCAN_API_KEY"},
            "routescan": {"base_url": "https://routescan.test"},
            "bsctrace_meganode": {"base_url": ""}}
    eth = build_provider("ethereum", 1, base)
    arb = build_provider("arbitrum", 42161, base)
    assert isinstance(eth, EtherscanV2Provider) and isinstance(arb, EtherscanV2Provider)
    assert eth.api_key == arb.api_key == "shared"
    assert isinstance(build_provider("base", 8453, base), RoutescanProvider)
    assert isinstance(build_provider("bsc", 56, base), MegaNodeProvider)


def test_provider_response_normalization_and_unsupported_capability():
    cfg = {"base_url": "https://etherscan.test", "api_key_env": "ETHERSCAN_API_KEY"}
    session = Session([Response({"status": "1", "result": [{"SourceCode": "contract X {}"}]}),
                       Response({"status": "1", "result": [{"TokenHolderAddress": "0x1"}]}),
                       Response({"status": "1", "result": [{"contractCreator": "0x2"}]})])
    result = EtherscanV2Provider(1, cfg, session, api_key="key").enrich("0xtoken")
    assert result.contract_verified.value is True
    assert result.holder_count == 1
    assert result.deployer_address.value == "0x2"
    unsupported = MegaNodeProvider({"base_url": ""}).enrich("0xtoken")
    assert unsupported.top_holders.status is CapabilityStatus.UNSUPPORTED


def test_routescan_keyless_mode_is_explicit_and_normalizes_holders():
    provider = RoutescanProvider(8453, {"base_url": "https://routescan.test", "allow_keyless": True,
                                       "keyless_requests_per_second": 1000},
                                 Session([Response({"items": [{"address": "0x1", "balance": "2"}]})]))
    result = provider.get_top_holders("0xtoken")
    assert result.status is CapabilityStatus.AVAILABLE and result.value[0]["balance"] == "2"
    disabled = RoutescanProvider(8453, {"base_url": "https://routescan.test"})
    assert disabled.get_top_holders("0xtoken").status is CapabilityStatus.UNSUPPORTED


def test_rpc_and_explorer_credentials_are_independent(monkeypatch):
    monkeypatch.setenv("EVM_RPC_URL_ETHEREUM", "https://rpc.example")
    monkeypatch.setenv("ETHERSCAN_API_KEY", "explorer-only")
    assert resolve_chain_rpc_url("ethereum") == "https://rpc.example"
    assert resolve_explorer_credential("ETHERSCAN_API_KEY") == "explorer-only"
    provider = EtherscanV2Provider(1, {"base_url": "https://x", "api_key_env": "ETHERSCAN_API_KEY"},
                                   api_key="explorer-only")
    assert provider.api_key == "explorer-only"


def test_explorer_credential_resolves_independently_of_rpc_availability(monkeypatch):
    monkeypatch.delenv("EVM_RPC_URL_ETHEREUM", raising=False)
    monkeypatch.setenv("ETHERSCAN_API_KEY", "explorer-only")
    assert resolve_explorer_credential("ETHERSCAN_API_KEY") == "explorer-only"
    with pytest.raises(MissingEnvironmentValueError):
        resolve_chain_rpc_url("ethereum")

    monkeypatch.setenv("EVM_RPC_URL_ETHEREUM", "https://rpc.example")
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    assert resolve_chain_rpc_url("ethereum") == "https://rpc.example"
    assert resolve_explorer_credential("ETHERSCAN_API_KEY") == ""


def test_permissive_rpc_resolution_represents_unconfigured_chain_without_raising(monkeypatch):
    monkeypatch.delenv("EVM_RPC_URL_ETHEREUM", raising=False)
    assert resolve_chain_rpc_url("ethereum", strict=False) == ""


def test_routescan_remains_keyless_when_allow_keyless_true_and_no_api_key(monkeypatch):
    monkeypatch.delenv("ROUTESCAN_API_KEY", raising=False)
    config = {"providers": {"base": "routescan"},
              "routescan": {"base_url": "https://routescan.test", "allow_keyless": True,
                            "keyless_requests_per_second": 5}}
    provider = build_provider("base", 8453, config)
    assert isinstance(provider, RoutescanProvider)
    assert provider.api_key == ""
    assert provider.keyless_enabled is True


def test_pair_created_decoding():
    pair = "0000000000000000000000001234567890123456789012345678901234567890"
    assert decode_created_asset({"topics": [PAIR_CREATED_TOPIC, "0x01", "0x02"], "data": "0x" + pair}) == "0x1234567890123456789012345678901234567890"


def test_listener_persists_enrichment_and_run(tmp_path):
    address = "0x1234567890123456789012345678901234567890"
    result = EnrichmentResult("fixture", Capability(CapabilityStatus.AVAILABLE, True),
                              Capability(CapabilityStatus.AVAILABLE, [{"address": "0xholder"}]),
                              Capability(CapabilityStatus.AVAILABLE, "0xdeployer"))
    class Provider:
        def enrich(self, address): return result
    class Risk:
        def screen(self, address, chain_id): return {"provider": "fixture", "summary": {"risk": "low"}}
    token0 = "0x1111111111111111111111111111111111111111"
    token1 = "0x2222222222222222222222222222222222222222"
    class RPC:
        def get_block(self, block_number):
            return fixture_block(block_number, format(block_number, "02x"),
                                 format(block_number - 1, "02x"))
        def get_factory_logs(self, factories, from_block, to_block):
            return [{"topics": [PAIR_CREATED_TOPIC, "0x" + "0" * 24 + token0[2:],
                                "0x" + "0" * 24 + token1[2:]],
                     "data": "0x" + "0" * 24 + address[2:],
                     "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc)}]
    db = str(tmp_path / "db.duckdb")
    assert observe_once({"name": "ethereum", "chain_id": 1, "factories": []}, RPC(), Provider(),
                        Risk(), db_path=db, from_block=1, to_block=2) == 1
    metadata = read_metadata(db)[0]
    assert metadata["holder_count"] == 1 and metadata["contract_verified"] is True
    flags = json.loads(metadata["risk_flags_json"])
    assert flags["risk"]["provider"] == "fixture"
    assert flags["enrichment"]["contract_verified"]["status"] == "AVAILABLE"
    assert read_events(db)[0]["event_type"] == "new_pool_detected"
    assert read_runs(db)[0]["status"] == "success"
    from storage.db import read_asset_relationships
    assert {row["asset_canonical_id"] for row in read_asset_relationships(db)} == {
        f"ethereum:{token0}", f"ethereum:{token1}"}


def test_listener_cursor_survives_restart_and_rejects_skipped_range(tmp_path):
    calls = []

    class RPC:
        def get_block(self, block_number):
            return fixture_block(block_number, format(block_number, "02x"),
                                 format(block_number - 1, "02x"))
        def get_factory_logs(self, factories, from_block, to_block):
            calls.append((from_block, to_block))
            return []

    class Provider:
        pass

    db = str(tmp_path / "cursor.duckdb")
    chain = {"name": "ethereum", "chain_id": 1, "factories": []}
    assert observe_once(chain, RPC(), Provider(), Provider(), db_path=db,
                        from_block=10, to_block=20, cursor_source="evm_rpc") == 0
    assert get_ingestion_cursor("evm_rpc", "ethereum", db)["position"] == 20
    assert observe_once(chain, RPC(), Provider(), Provider(), db_path=db,
                        from_block=21, to_block=25, cursor_source="evm_rpc") == 0
    assert get_ingestion_cursor("evm_rpc", "ethereum", db)["position"] == 25
    try:
        observe_once(chain, RPC(), Provider(), Provider(), db_path=db,
                     from_block=27, to_block=30, cursor_source="evm_rpc")
    except ValueError as exc:
        assert "skipped block range" in str(exc)
    else:
        raise AssertionError("a skipped block range should fail closed")
    assert calls == [(10, 20), (21, 25)]
    assert get_ingestion_cursor("evm_rpc", "ethereum", db)["position"] == 25


def test_listener_reconciles_short_reorg_without_deleting_block_evidence(tmp_path):
    hashes = {100: "aa", 101: "bb"}

    class RPC:
        def get_block(self, block_number):
            parent = hashes.get(block_number - 1, "99")
            return fixture_block(block_number, hashes[block_number], parent)
        def get_factory_logs(self, factories, from_block, to_block): return []

    db = str(tmp_path / "reorg.duckdb")
    chain = {"name": "ethereum", "chain_id": 1, "factories": []}
    assert observe_once(chain, RPC(), object(), object(), db_path=db, from_block=100,
                        to_block=101, cursor_source="evm_rpc") == 0
    insert_event({"canonical_id": "ethereum:0xpool", "event_type": "new_pool_detected",
                  "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc), "payload_json": {},
                  "source": "evm_rpc", "block_number": 100,
                  "block_hash": "0x" + "aa" * 32}, db)
    hashes[100] = "cc"
    hashes[101] = "dd"
    assert observe_once(chain, RPC(), object(), object(), db_path=db, from_block=100,
                        to_block=101, cursor_source="evm_rpc") == 0

    rows = read_evm_block_observations(db)
    assert [(row["block_number"], row["block_hash"], row["canonical"]) for row in rows] == [
        (100, "0x" + "aa" * 32, False), (100, "0x" + "cc" * 32, True),
        (101, "0x" + "bb" * 32, False), (101, "0x" + "dd" * 32, True),
    ]
    reorgs = [row for row in read_events(db) if row["event_type"] == "chain_reorg_detected"]
    assert len(reorgs) == 2
    assert {json.loads(row["payload_json"])["block_number"] for row in reorgs} == {100, 101}
    assert not [row for row in read_events(db) if row["event_type"] == "new_pool_detected"]
    orphaned = [row for row in read_event_history(db) if row["event_type"] == "new_pool_detected"]
    assert len(orphaned) == 1 and orphaned[0]["canonical"] is False

def test_chain_configuration_contains_all_required_evm_networks():
    from ingestion.evm.config import load_chain
    assert {load_chain(name)["chain_id"] for name in ("ethereum", "base", "arbitrum", "bsc")} == {1, 8453, 42161, 56}


def test_config_failure_is_recorded_as_failed_run(tmp_path, monkeypatch):
    monkeypatch.delenv("EVM_RPC_URL_ETHEREUM", raising=False)
    db = str(tmp_path / "db.duckdb")
    with pytest.raises(MissingEnvironmentValueError) as excinfo:
        run_once("ethereum", db_path=db)
    assert "EVM_RPC_URL_ETHEREUM" in str(excinfo.value)
    run_row = read_runs(db)[0]
    assert run_row["status"] == "failed"
    # storage.db.safe_error_message redacts anything matching an `rpc_url`-shaped token
    # before persisting, so the persisted record carries the redaction, not the raw key.
    assert "missing required environment value" in run_row["error_message"]
    assert "[REDACTED]" in run_row["error_message"]


def test_missing_rpc_url_fails_before_any_network_call(tmp_path, monkeypatch):
    monkeypatch.delenv("EVM_RPC_URL_ETHEREUM", raising=False)

    class NetworkCallDuringConfig(AssertionError):
        pass

    class RPC:
        def __init__(self, rpc_url):
            raise NetworkCallDuringConfig("RPC client must not be constructed before RPC URL resolution")

    import ingestion.evm.listener as listener_module
    monkeypatch.setattr(listener_module, "EVMRPCClient", RPC)

    db = str(tmp_path / "db.duckdb")
    with pytest.raises(MissingEnvironmentValueError):
        run_once("ethereum", db_path=db)


def test_missing_rpc_url_error_never_leaks_a_credential_value(monkeypatch):
    monkeypatch.delenv("EVM_RPC_URL_ETHEREUM", raising=False)
    monkeypatch.setenv("ETHERSCAN_API_KEY", "sk-super-secret-should-never-leak")
    with pytest.raises(MissingEnvironmentValueError) as excinfo:
        resolve_chain_rpc_url("ethereum")
    assert "sk-super-secret-should-never-leak" not in str(excinfo.value)
