"""
End-to-end correctness — agent responses are checked against gold reference
answers derived from the Confluence knowledge base.

Cases are defined in cases/correctness.yaml.
To add a test: edit the YAML. No Python changes needed.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import load_yaml
from tests.utils import agent_runner
from tests.utils.judge_model import judge_model

CASES = load_yaml("correctness.yaml")

correctness_metric = GEval(
    name="Factual correctness",
    model=judge_model,
    criteria=(
        "The agent's response must contain the key facts from the expected "
        "output. Check that specific numbers, definitions, procedures, and "
        "named entities match. The response may use a different language "
        "than the expected output (e.g. Norwegian vs English) — evaluate "
        "semantic equivalence, not literal wording. Minor omissions of "
        "non-essential details are acceptable, but core facts must be present "
        "and accurate."
    ),
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.7,
)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_correctness(case: dict):
    result = agent_runner.run(case["input"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=result.answer,
        expected_output=case["expected_output"],
    )
    assert_test(test_case, [correctness_metric])
