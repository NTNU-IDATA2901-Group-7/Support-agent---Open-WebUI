"""
Retrieval — assert that expected ticket keys appear in vector search results.

Cases are defined in cases/retrieval.yaml.
Deterministic assertions — no LLM judge needed.
"""

import re

import pytest

from tests.conftest import load_yaml
from tests.utils import agent_runner

CASES = load_yaml("retrieval.yaml")

_KEY_RE = re.compile(r"Key:\s*(\S+)")


def _extract_retrieved_keys(tool_calls: list[dict]) -> set[str]:
    """Extract ticket keys from vector search tool results."""
    keys = set()
    for tc in tool_calls:
        if not tc.get("done"):
            continue
        result = tc.get("result")
        if not result:
            continue
        text = result if isinstance(result, str) else str(result)
        keys.update(_KEY_RE.findall(text))
    return keys


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_retrieval(case: dict):
    result = agent_runner.run(case["input"])
    retrieved_keys = _extract_retrieved_keys(result.tool_calls)
    expected_keys = set(case["expected_keys"])

    assert expected_keys.issubset(retrieved_keys), (
        f"Expected keys {expected_keys} not found in retrieved keys {retrieved_keys}"
    )
