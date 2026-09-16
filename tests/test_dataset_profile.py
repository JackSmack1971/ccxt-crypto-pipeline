from datetime import datetime

from analysis.datasets import (Asset, Bar, DatasetPolicy, DatasetSnapshot, build_dataset_profile,
                               verify_dataset_profile, write_dataset_profile)


def _dataset():
    t0 = datetime(2025, 1, 1)
    asset = Asset("ethereum:aaa", "dex", "ethereum", "0xaaa", t0, "0xaaa")
    bars = (
        Bar(asset.canonical_id, t0, 1, 1, 1, 1, 10, "1h", "fixture"),
        Bar(asset.canonical_id, datetime(2025, 1, 1, 2), 1, 1, 1, 1, 10, "1h", "fixture"),
        Bar(asset.canonical_id, datetime(2025, 1, 1, 4), 1, 1, 1, 1, 10, "1h", "fixture"),
    )
    return DatasetSnapshot((asset,), bars, (), (), (), DatasetPolicy(
        query_policy_version="profile-test", timeframe="1h", start=t0,
        end=datetime(2025, 1, 1, 4)), "dataset-test", quote_assets={asset.canonical_id: "ethereum:eur"})


def test_profile_is_explicit_deterministic_and_binds_dataset_identity():
    first = build_dataset_profile(_dataset(), label_horizons=("1h",))
    second = build_dataset_profile(_dataset(), label_horizons=("1h",))
    assert first == second
    assert first["dataset_identity"] == "dataset-test"
    assert first["profile_identity"]
    assert first["coverage"][0]["missing"] == 2
    assert first["missingness"]["gaps"][0]["max_internal_gap_periods"] == 1
    assert first["censoring"]["quote_conversion_gaps"][0]["status"] == "unavailable"
    assert first["representativeness"]["status"] == "unavailable"
    assert verify_dataset_profile(first, "dataset-test") == first["profile_identity"]


def test_profile_artifact_is_immutable_and_replayable(tmp_path):
    profile = build_dataset_profile(_dataset())
    first = write_dataset_profile(profile, tmp_path)
    second = write_dataset_profile(build_dataset_profile(_dataset()), tmp_path)
    assert first == second
    assert first.read_bytes() == second.read_bytes()
