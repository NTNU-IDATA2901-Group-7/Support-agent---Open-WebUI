"""
End-to-end answer relevancy.

Cases are defined in cases/relevancy.yaml.
To add a test: edit the YAML. No Python changes needed.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

from tests.conftest import load_yaml
from tests.utils import agent_runner
from tests.utils.judge_model import judge_model

CASES = load_yaml("relevancy.yaml")

relevancy_metric = AnswerRelevancyMetric(
    model=judge_model,
    threshold=0.7,
    include_reason=True,
)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_relevancy(case: dict):
    result = agent_runner.run(case["input"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=result.answer,
    )
    assert_test(test_case, [relevancy_metric])
