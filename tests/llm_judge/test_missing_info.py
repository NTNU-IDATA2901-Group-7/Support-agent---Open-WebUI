"""
Missing info detection — agent should ask for clarification when the query
lacks key details needed to help.

Cases are defined in cases/missing_info.yaml.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import load_yaml
from tests.utils import agent_runner
from tests.utils.judge_model import judge_model

CASES = load_yaml("missing_info.yaml")

missing_info_metric = GEval(
    name="Missing info detection",
    model=judge_model,
    criteria=(
        "The user's query is missing key information needed to help them "
        "(such as a ticket number, order reference, error message, or specific "
        "details about what system or feature is affected). "
        "Did the agent ask the user for the missing information instead of "
        "guessing, giving a generic answer, or proceeding with a tool call "
        "that cannot succeed without the missing details?"
    ),
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
    ],
    threshold=0.7,
)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_missing_info(case: dict):
    result = agent_runner.run(case["input"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=result.answer,
    )
    assert_test(test_case, [missing_info_metric])
