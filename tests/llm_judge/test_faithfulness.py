"""
Faithfulness — checks that the agent's answer is grounded in the retrieved
context and does not hallucinate facts beyond what was provided.

Uses retrieval test cases which trigger the vector search tool. The
retrieval context is extracted from tool call results (not knowledge base
sources) since these tests run without pre-injected files.
"""

import deepeval
import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from tests.conftest import (
    AGENT_MODEL,
    SYSTEM_PROMPT,
    common_hyperparameters,
    load_yaml,
    rag_hyperparameters,
    tool_hyperparameters,
)
from tests.utils import agent_runner
from tests.utils.judge_model import judge_model

CASES = load_yaml("retrieval.yaml")


@deepeval.log_hyperparameters
def hyperparameters():
    return {
        "model": AGENT_MODEL,
        "prompt_template": SYSTEM_PROMPT,
        **common_hyperparameters(),
        **rag_hyperparameters(),
        **tool_hyperparameters(),
    }


faithfulness_metric = FaithfulnessMetric(
    model=judge_model,
    threshold=0.7,
    include_reason=True,
)


def _extract_tool_result_context(tool_calls: list[dict]) -> list[str]:
    """Extract retrieval context from tool call results."""
    contexts = []
    for tc in tool_calls:
        if not tc.get("done"):
            continue
        result = tc.get("result")
        if not result:
            continue
        text = result if isinstance(result, str) else str(result)
        if text:
            contexts.append(text)
    return contexts


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_faithfulness(case: dict):
    result = agent_runner.run(case["input"], include_files=False)
    retrieval_context = _extract_tool_result_context(result.tool_calls)

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=result.answer,
        retrieval_context=retrieval_context,
    )

    faithfulness_metric.measure(test_case)
    print(
        f"[faithfulness] case={case['id']}\n"
        f"  score={faithfulness_metric.score:.3f}\n"
        f"  reason={faithfulness_metric.reason}"
    )

    assert_test(test_case, [faithfulness_metric])
