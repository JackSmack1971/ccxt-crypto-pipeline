"""Offline acceptance evidence for the Phase 8R falsification boundary."""

import pytest
import json

from analysis.experiments import (FalsificationPolicy, build_falsification_evidence,
                                  load_run, run_experiment)
from test_phase6 import runner_snapshot, runner_spec


def _controls(difference=0.0):
    return {"status": "available", "results": [{"method": "label_permutation",
            "candidate": {"baseline_comparison": {"difference": difference}}},
            {"method": "known_null", "candidate": {"baseline_comparison": {"difference": difference}}}]}


def test_falsification_requires_every_declared_method_and_is_deterministic():
    policy = FalsificationPolicy(methods=("label_permutation", "known_null", "leave_one_out"))
    stability = {"status": "available", "dimensions": {"leave_one_out": [
        {"excluded_token_id": "a", "remaining_sample_size": 0,
         "mean_return": 0.1, "baseline_mean_return": 0.1}]}}
    first = build_falsification_evidence(policy=policy, negative_controls=_controls(), stability=stability)
    assert first == build_falsification_evidence(policy=policy, negative_controls=_controls(), stability=stability)
    assert first["status"] == "passed"
    assert all(row["status"] == "passed" for row in first["results"])
    assert first["selection"] == "all_declared_methods_required"


def test_falsification_distinguishes_failed_and_unavailable_evidence():
    failed = build_falsification_evidence(
        policy=FalsificationPolicy(methods=("known_null",)),
        negative_controls={"status": "available", "results": [{"method": "known_null",
            "candidate": {"baseline_comparison": {"difference": 0.1}}}]}, stability={})
    unavailable = build_falsification_evidence(
        policy=FalsificationPolicy(methods=("source_substitution",)),
        negative_controls=_controls(), stability={})
    assert failed["status"] == "failed"
    assert failed["results"][0]["reason"] == "NULL_CONTROL_OUTPERFORMED_BASELINE"
    assert unavailable["status"] == "unavailable"
    assert unavailable["results"][0]["reason"] == "METHOD_NOT_IMPLEMENTED"

    inapplicable = build_falsification_evidence(
        policy=FalsificationPolicy(methods=("leave_chain_out",), inapplicable_methods=("leave_chain_out",)),
        negative_controls={}, stability={})
    assert inapplicable["status"] == "inapplicable"
    assert inapplicable["results"][0]["status"] == "inapplicable"
    with pytest.raises(ValueError, match="was not declared"):
        FalsificationPolicy(methods=("known_null",), inapplicable_methods=("leave_chain_out",))


def test_falsification_policy_rejects_posthoc_or_ambiguous_declarations():
    with pytest.raises(ValueError, match="unsupported falsification method"):
        FalsificationPolicy(methods=("invented_test",))
    with pytest.raises(ValueError, match="must be unique"):
        FalsificationPolicy(methods=("known_null", "known_null"))


def test_falsification_rejects_malformed_leave_one_out_evidence():
    result = build_falsification_evidence(
        policy=FalsificationPolicy(methods=("leave_one_out",)), negative_controls={},
        stability={"status": "available", "dimensions": {"leave_one_out": [{}]}})
    assert result["status"] == "unavailable"
    assert result["results"][0]["reason"] == "EVIDENCE_INCOMPLETE"


def test_falsification_does_not_promote_failed_or_unknown_upstream_evidence():
    for status in ("failed", "unknown", None):
        result = build_falsification_evidence(
            policy=FalsificationPolicy(methods=("known_null",)),
            negative_controls={"status": status, "results": [{"method": "known_null",
                "candidate": {"baseline_comparison": {"difference": 0.0}}}]}, stability={})
        assert result["status"] == "unavailable"


def test_catalog_binds_falsification_policy_to_spec(tmp_path):
    run = run_experiment(runner_spec(), runner_snapshot(), tmp_path / "runs")
    manifest = json.loads((run / "manifest.json").read_text())
    falsification = json.loads((run / "falsification.json").read_text())
    falsification["policy"]["methods"] = ["known_null"]
    falsification_path = run / "falsification.json"
    falsification_path.write_text(json.dumps(falsification, sort_keys=True, separators=(",", ":")) + "\n")
    import hashlib
    manifest["artifacts"]["falsification.json"] = hashlib.sha256(falsification_path.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="falsification policy mismatch"):
        load_run(run)
