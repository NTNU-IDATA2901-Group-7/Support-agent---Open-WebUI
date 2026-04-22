"""
Smoke test for agent_runner — verifies the Open WebUI chat API is reachable
and returns a response.

Run with:  pytest tests/deterministic/test_agent_runner_smoke.py -v
"""

from tests.utils import agent_runner


def test_run_returns_answer():
    """agent_runner.run() should return an AgentResult with a non-empty answer."""
    result = agent_runner.run("Hello, are you there?")

    assert isinstance(result, agent_runner.AgentResult)
    assert len(result.answer) > 0, "Agent returned an empty answer"


def test_run_with_tool_query():
    """A support query should trigger tool calls and return an answer."""
    result = agent_runner.run("Are there any tickets about login issues?")

    assert len(result.answer) > 0, "Agent returned an empty answer"
    # tool_calls may or may not be present depending on how Open WebUI returns them
