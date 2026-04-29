"""
Ticket escalation — agent should suggest escalating when it cannot resolve the issue.

Cases are defined in cases/escalation.yaml.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import load_yaml
from tests.utils import agent_runner
from tests.utils.judge_model import judge_model

CASES = load_yaml("escalation.yaml")

escalation_metric = GEval(
    name="Ticket escalation",
    model=judge_model,
    criteria=(
        "When the issue is clearly beyond what the agent can resolve through "
        "its knowledge base — such as data loss, production outages, or "
        "infrastructure failures — did the agent acknowledge this and "
        "explicitly suggest escalating to a support ticket or human agent, "
        "rather than attempting to answer with inadequate information or "
        "returning an empty/generic response?"
    ),
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
    ],
    threshold=0.7,
)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_escalation(case: dict):
    result = agent_runner.run(case["input"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=result.answer,
    )
    assert_test(test_case, [escalation_metric])
