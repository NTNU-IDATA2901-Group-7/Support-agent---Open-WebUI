"""
Ticket-grounded correctness — does the agent produce the right resolution
given the retrieved ticket cluster?

Cases in cases/ticket_correctness.yaml come from closed support tickets
with documented resolutions. Each case has a customer-style query, the
expected ticket key(s) for per-case retrieval attribution, and a gold
resolution.

End-to-end grading. retrieval_context is attached to the LLMTestCase so
that on Confident AI you can drill into a failed case and see whether
the failure came from retrieval (wrong cluster surfaced) or synthesis
(right cluster, wrong answer extracted).
"""

import re

import deepeval
import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

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

CASES = load_yaml("ticket_correctness.yaml")

_KEY_RE = re.compile(r"Key:\s*(\S+)")


@deepeval.log_hyperparameters
def hyperparameters():
    return {
        "model": AGENT_MODEL,
        "prompt_template": SYSTEM_PROMPT,
        **common_hyperparameters(),
        **rag_hyperparameters(),
        **tool_hyperparameters(),
    }


class RetrievalAttributionMetric(BaseMetric):
    """Diagnostic: surfaces retrieved vs expected ticket keys on the
    Confident AI metric-data panel, so a failed case can be attributed
    to retrieval (cluster miss) vs synthesis (wrong answer from the
    right cluster) without leaving the metric view."""

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.score = 0.0
        self.reason = ""
        self.success = False

    def measure(self, test_case: LLMTestCase) -> float:
        meta = test_case.additional_metadata or {}
        retrieved = list(meta.get("retrieved_keys", []))
        expected = list(meta.get("expected_keys", []))
        cluster_hit = bool(meta.get("cluster_hit", False))
        self.score = 1.0 if cluster_hit else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Retrieved ({len(retrieved)}): "
            f"{', '.join(retrieved) if retrieved else '(none)'}\n"
            f"Expected: {', '.join(sorted(expected)) if expected else '(none)'}\n"
            f"Cluster hit: {cluster_hit}"
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self) -> str:
        return "Retrieval attribution"


retrieval_attribution_metric = RetrievalAttributionMetric()


ticket_correctness_metric = GEval(
    name="Ticket Answer Correctness",
    model=judge_model,
    evaluation_steps=[
        "Identify the key resolution facts in the expected output: "
        "causes, fixes, workarounds, deployment state (deployed / planned "
        "/ under investigation / workaround only), and concrete actions.",
        "For each key fact, check whether it is present and accurate in "
        "the actual output.",
        "The response may use a different language than the expected output "
        "(e.g. Norwegian vs English) — evaluate semantic equivalence, not "
        "literal wording.",
        "Minor omissions of non-essential context are acceptable, but the "
        "core cause and the deployment state must be present. If the gold "
        "says 'no fix deployed yet', the agent must reflect that and not "
        "present the cause's mechanism as a deployed resolution.",
        "Penalize each of: stating no resolution exists when one does; "
        "naming a different cause or fix; claiming a fix is deployed when "
        "the gold says it is planned, proposed, or unresolved; "
        "hallucinating fixes or steps not in the gold answer; deferring "
        "to human support / suggesting opening a new ticket when the gold "
        "provides a concrete action the agent could have stated.",
    ],
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.7,
)


def _extract_retrieved_keys(tool_calls: list[dict]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for tc in tool_calls:
        if not tc.get("done"):
            continue
        result = tc.get("result")
        if not result:
            continue
        text = result if isinstance(result, str) else str(result)
        for key in _KEY_RE.findall(text):
            if key not in seen:
                keys.append(key)
                seen.add(key)
    return keys


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_ticket_correctness(case: dict):
    result = agent_runner.run(case["input"])
    retrieved_keys = _extract_retrieved_keys(result.tool_calls)

    expected_keys = set(case["expected_keys"])
    cluster_hit = bool(expected_keys & set(retrieved_keys))

    header = (
        f"=== Retrieved ticket keys (in rank order): "
        f"{', '.join(retrieved_keys) if retrieved_keys else '(none)'}\n"
        f"=== Expected ticket keys: {', '.join(sorted(expected_keys))}\n"
        f"=== Cluster hit: {cluster_hit}"
    )

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=result.answer,
        expected_output=case["expected_output"],
        retrieval_context=[header],
        additional_metadata={
            "expected_keys": list(expected_keys),
            "retrieved_keys": retrieved_keys,
            "cluster_hit": cluster_hit,
        },
    )
    assert_test(test_case, [ticket_correctness_metric, retrieval_attribution_metric])
