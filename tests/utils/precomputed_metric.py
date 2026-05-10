"""
PrecomputedMetric — wraps a deterministically computed score as a DeepEval metric
so it can be shipped to Confident AI alongside LLM-judged metrics.

Useful for retrieval-style tests where precision@k, recall@k, MRR, etc. are
computed in plain Python and don't need an LLM judge — but we still want them
visible on the dashboard.

Note: instance attribute names must match constructor parameter names so that
DeepEval's internal `copy_metrics()` (which uses `vars(self)`) can rebuild the
metric instance when it ships test cases to Confident AI.
"""

from __future__ import annotations

from deepeval.metrics import BaseMetric


class PrecomputedMetric(BaseMetric):
    """A DeepEval metric whose score was computed before `measure()` was called.

    `measure()` ignores the test case and just confirms the precomputed score.
    No LLM is called.
    """

    def __init__(
        self,
        name: str,
        score: float,
        threshold: float,
        reason: str = "",
        evaluation_model: str = "deterministic",
    ):
        self.name = name
        self.score = score
        self.threshold = threshold
        self.reason = reason
        self.evaluation_model = evaluation_model
        self.success = score >= threshold
        self.error: str | None = None

    def measure(self, test_case) -> float:
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self) -> str:
        return self.name
