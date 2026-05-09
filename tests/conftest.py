"""
Shared fixtures and configuration for the test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CASES = Path(__file__).parent / "cases"


# ── Fixtures ─────────────────────────────────────────────────────


def load_yaml(filename: str) -> list[dict]:
    """Load a YAML file from the test/cases/ directory and return the list of test cases.

    Test files call this to load their ground-truth data, e.g. load_yaml("correctness.yaml").
    Each YAML file contains a list of dicts with fields like id, input, expected_output, etc.
    """
    path = CASES / filename
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session", autouse=True)
def teardown_agent_client():
    """Session-scoped fixture that cleans up the agent_runner's HTTP client.

    Runs automatically (autouse=True) for the entire test session. The yield
    lets all tests run first, then agent_runner.close() fires once at the end
    to release the httpx connection used to talk to Open WebUI.

    Only imports agent_runner if it was actually used (i.e., llm_judge tests ran).
    Deterministic tests skip this entirely.
    """
    yield
    try:
        from tests.utils import agent_runner

        agent_runner.close()
    except ImportError:
        pass


# ── Markers ──────────────────────────────────────────────────────


def pytest_collection_modifyitems(items):
    """Auto-tag tests with markers based on their directory.

    Tests under test/llm_judge/   get @pytest.mark.llm_judge
    Tests under test/assertion_based/ get @pytest.mark.assertion_based

    This lets us run subsets selectively:
        pytest -m assertion_based   # fast smoke tests, no LLM calls
        pytest -m llm_judge         # slow tests scored by DeepEval, costs API tokens
    """
    for item in items:
        path = str(item.fspath)
        if "llm_judge" in path:
            item.add_marker(pytest.mark.llm_judge)
        if "assertion_based" in path:
            item.add_marker(pytest.mark.assertion_based)
