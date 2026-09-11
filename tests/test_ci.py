from pathlib import Path

import yaml


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"


def _workflow():
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_ci_runs_for_pull_requests_and_main():
    triggers = _workflow()["on"]

    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]
    assert _workflow()["permissions"] == {"contents": "read"}


def test_ci_uses_locked_inputs_and_required_repository_checks():
    workflow = _workflow()
    jobs = workflow["jobs"]

    assert list(jobs) == ["fixture-verification"]
    steps = jobs["fixture-verification"]["steps"]
    actions = [step["uses"] for step in steps if "uses" in step]
    commands = "\n".join(step["run"] for step in steps if "run" in step)
    uv_setup = next(step for step in steps if step.get("uses") == "astral-sh/setup-uv@v6")

    assert actions == ["actions/checkout@v4", "astral-sh/setup-uv@v6"]
    assert uv_setup["with"] == {"enable-cache": "true", "python-version": "3.12"}
    assert "uv sync --locked" in commands
    assert "uv pip install pytest==9.0.3" in commands
    assert "tests/test_storage.py::test_v1_store_migrates_in_place_and_preserves_rows" in commands
    assert "uv run --no-sync python -m pytest" in commands
    assert "python -m compileall" in commands
    assert "git diff --check" in commands


def test_fixture_ci_has_no_provider_credentials_or_live_commands():
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8").lower()

    forbidden = ("api_key", "rpc_url", "secret", "scheduler --once", "backfill", "live")
    assert not any(term in workflow_text for term in forbidden)
