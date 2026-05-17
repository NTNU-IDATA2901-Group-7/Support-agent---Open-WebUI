"""
Ticket escalation — does the agent know WHEN to escalate AND WHEN NOT TO?

Cases are defined in cases/escalation.yaml with per-case criteria graded
against an urgency tier (critical / high / medium / low). The metric name
is shared so Confident AI aggregates across the suite; the urgency tier
ships as metadata for per-tier stratification on the dashboard.
"""

import deepeval
import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import AGENT_MODEL, SYSTEM_PROMPT, common_hyperparameters, load_yaml
from tests.utils import agent_runner
from tests.utils.judge_model import judge_model

CASES = load_yaml("escalation.yaml")


@deepeval.log_hyperparameters
def hyperparameters():
    return {
        "model": AGENT_MODEL,
        "prompt_template": SYSTEM_PROMPT,
        **common_hyperparameters(),
    }


def _escalation_metric(criteria: str) -> GEval:
    return GEval(
        name="Ticket escalation",
        model=judge_model,
        criteria=criteria,
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
        tags=[case["urgency"]],
    )
    assert_test(test_case, [_escalation_metric(case["criteria"])])
