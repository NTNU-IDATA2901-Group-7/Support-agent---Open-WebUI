"""
Tool selection — agent should pick the correct tool (or no tool) for each query.

Cases are defined in cases/tool_selection.yaml.
Deterministic assertions — no LLM judge needed.
"""

import pytest

from tests.conftest import load_yaml
from tests.utils import agent_runner

CASES = load_yaml("tool_selection.yaml")


def _normalize_tool_name(name: str) -> str:
    """Strip mcpo/OpenAPI wrapping from tool names.

    mcpo exposes tools as ``tool_<original>_post``. Strip that so test
    cases can use the plain MCP tool names.
    """
    if name.startswith("tool_") and name.endswith("_post"):
        return name[len("tool_") : -len("_post")]
    return name


def _extract_tool_names(tool_calls: list[dict]) -> set[str]:
    """Extract normalized tool function names from parsed tool calls."""
    return {_normalize_tool_name(tc["name"]) for tc in tool_calls if tc.get("done")}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_tool_selection(case: dict):
    result = agent_runner.run(case["input"])
    actual_tools = _extract_tool_names(result.tool_calls)
    expected_tools = set(case["expected_tools"])

    if expected_tools:
        assert expected_tools.issubset(
            actual_tools
        ), f"Expected tools {expected_tools} not found in {actual_tools}"
    else:
        assert len(actual_tools) == 0, f"Expected no tools, but got {actual_tools}"
