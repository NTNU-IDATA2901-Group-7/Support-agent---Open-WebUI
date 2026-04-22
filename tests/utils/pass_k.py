"""
pass^k reliability wrapper.

Runs a test multiple times and returns the fraction that passed.
Supports two modes:

  1. Agent variance   — re‑run the *agent* k times on the same query,
                        then evaluate each result once.
  2. Judge variance   — run the agent once, then evaluate the *same*
                        result k times with the LLM judge.

You can (and should) run both to separate agent non‑determinism
from judge non‑determinism.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


@dataclass
class PassKResult:
    k: int
    passes: int
    rate: float
    scores: list[float]


def pass_k_agent(
    build_test_case: Callable[[], LLMTestCase],
    metric: BaseMetric,
    k: int = 5,
) -> PassKResult:
    """
    Re‑invoke the agent k times (via build_test_case) and evaluate each.

    `build_test_case` should call agent_runner.run() internally so
    that each invocation produces a fresh agent response.

    Example
    -------
    >>> from tests.utils import agent_runner
    >>> def _build():
    ...     result = agent_runner.run("Hvordan setter jeg opp skanner?")
    ...     return LLMTestCase(
    ...         input="Hvordan setter jeg opp skanner?",
    ...         actual_output=result.answer,
    ...         retrieval_context=result.retrieval_context,
    ...     )
    >>> pk = pass_k_agent(_build, FaithfulnessMetric(threshold=0.7), k=5)
    >>> assert pk.rate >= 0.8
    """
    scores: list[float] = []
    passes = 0

    for _ in range(k):
        test_case = build_test_case()
        metric.measure(test_case)
        scores.append(metric.score)
        if metric.score >= metric.threshold:
            passes += 1

    return PassKResult(k=k, passes=passes, rate=passes / k, scores=scores)


def pass_k_judge(
    test_case: LLMTestCase,
    metric: BaseMetric,
    k: int = 5,
) -> PassKResult:
    """
    Evaluate the *same* agent output k times to measure judge variance.

    Example
    -------
    >>> pk = pass_k_judge(test_case, GEval(...), k=5)
    >>> assert pk.rate >= 0.8
    """
    scores: list[float] = []
    passes = 0

    for _ in range(k):
        metric.measure(test_case)
        scores.append(metric.score)
        if metric.score >= metric.threshold:
            passes += 1

    return PassKResult(k=k, passes=passes, rate=passes / k, scores=scores)
