"""
Language consistency — agent should respond in the same language as the user.

Cases are defined in cases/language.yaml.
"""

import deepeval
import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import AGENT_MODEL, SYSTEM_PROMPT, common_hyperparameters, load_yaml
from tests.utils import agent_runner
from tests.utils.judge_model import judge_model

CASES = load_yaml("language.yaml")


@deepeval.log_hyperparameters
def hyperparameters():
    return {
        "model": AGENT_MODEL,
        "prompt_template": SYSTEM_PROMPT,
        **common_hyperparameters(),
    }


def _language_metric(expected_language: str) -> GEval:
    return GEval(
        name="Language consistency",
        model=judge_model,
        criteria=(
            f"The user wrote in {expected_language}. Did the agent respond entirely "
            f"in {expected_language}? Isolated technical terms (e.g. 'WMS', "
            "'Bluetooth', 'barcode scanner') in English are acceptable, but full "
            "sentences, explanations, or instructions in the wrong language "
            "constitute a failure."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=0.7,
    )


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_language_consistency(case: dict):
    result = agent_runner.run(case["input"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=result.answer,
    )
    assert_test(test_case, [_language_metric(case["expected_language"])])
