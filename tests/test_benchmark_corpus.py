import json
import subprocess
import sys

import pytest

from analysis.benchmarks import (BENCHMARK_VERSION, benchmark_cases, benchmark_identity,
                                 verify_benchmark_results)


def test_corpus_declares_all_required_methodological_cases():
    cases = benchmark_cases()
    assert len(cases) == 12
    assert {case.case_id for case in cases} == {
        "random_signal", "future_feature", "survivorship_biased_universe", "known_null",
        "known_effect", "duplicate_observations", "future_liquidity", "insufficient_sample",
        "discovery_only_overfit", "unstable_cross_source", "missing_conversion", "ambiguous_identity",
    }
    assert {case.expected_outcome for case in cases} == {"pass", "reject", "block"}


def test_corpus_identity_and_results_are_deterministic():
    expected = {case.case_id: case.expected_outcome for case in benchmark_cases()}
    assert benchmark_identity() == benchmark_identity()
    verify_benchmark_results(expected)
    with pytest.raises(ValueError, match="exactly the declared cases"):
        verify_benchmark_results({})
    with pytest.raises(ValueError, match="outcome mismatch"):
        verify_benchmark_results({**expected, "random_signal": "pass"})


def test_cli_emits_replayable_contract():
    result = subprocess.run([sys.executable, "-m", "analysis.benchmarks"], check=True,
                            capture_output=True, text=True)
    payload = json.loads(result.stdout)
    assert payload["version"] == BENCHMARK_VERSION
    assert payload["identity"] == benchmark_identity()
    assert len(payload["cases"]) == 12
