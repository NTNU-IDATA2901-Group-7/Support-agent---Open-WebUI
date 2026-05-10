"""
Retrieval — assertion-based key-based retrieval evaluation.

Cases are defined in cases/retrieval.yaml.

Supports:
  - expected key labels
  - precision@k
  - R_cap@k (capped recall: hits / min(k, |relevant|); reaches 1.0 when top-k
    is filled with relevant docs, avoiding the raw recall@k ceiling when
    |relevant| > k — see BEIR, Thakur et al. 2021)
  - NDCG@k (self-normalizing graded ranking metric; Järvelin & Kekäläinen 2002)

Thresholds are configured globally in this file to keep case authoring simple.
"""

import math
import os
import re

import deepeval
import pytest
from deepeval import assert_test
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
from tests.utils.precomputed_metric import PrecomputedMetric

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


_KEY_RE = re.compile(r"Key:\s*(\S+)")

RETRIEVAL_K = int(os.environ.get("RETRIEVAL_K", "5"))
MIN_PRECISION_AT_K = float(os.environ.get("MIN_PRECISION_AT_K", "0.5"))
MIN_R_CAP_AT_K = float(os.environ.get("MIN_R_CAP_AT_K", "0.5"))
MIN_NDCG = float(os.environ.get("MIN_NDCG", "0.5"))
RETRIEVAL_VERBOSE = os.environ.get("RETRIEVAL_VERBOSE", "1") == "1"
EXPECTED_RETRIEVAL_TOOL = "search_vector_db_for_similar_jira_tickets_tool"

# Collect per-case metrics for aggregate summary
_results: list[dict] = []


def _classify_case(case_id: str) -> str:
    """Bucket a case by what it tests, for stratified aggregate metrics.

    Categories:
      - negative:   no relevant tickets exist (pass = nothing retrieved)
      - paraphrase: same gold as an original case, different surface form
      - english:    English query against the Norwegian corpus
      - original:   the baseline Norwegian phrasing
    """
    if case_id.startswith("negative_"):
        return "negative"
    if case_id.endswith("_paraphrase"):
        return "paraphrase"
    if case_id.endswith("_english"):
        return "english"
    return "original"


def _extract_retrieved_keys(tool_calls: list[dict]) -> list[str]:
    """Extract ranked ticket keys from vector search tool results."""
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


def _extract_search_queries(tool_calls: list[dict]) -> list[str]:
    """Extract the search_text arguments the model sent to the vector search tool."""
    queries = []
    for tc in tool_calls:
        args = tc.get("arguments")
        if not args:
            continue
        if isinstance(args, dict) and "search_text" in args:
            queries.append(args["search_text"])
        elif isinstance(args, str):
            try:
                import json

                parsed = json.loads(args)
                if "search_text" in parsed:
                    queries.append(parsed["search_text"])
            except (json.JSONDecodeError, ValueError):
                pass
    return queries


def _normalize_tool_name(name: str) -> str:
    if name.startswith("tool_") and name.endswith("_post"):
        return name[len("tool_") : -len("_post")]
    return name


def _extract_tool_names(tool_calls: list[dict]) -> list[str]:
    names = []
    for tc in tool_calls:
        name = tc.get("name")
        if not name:
            continue
        names.append(_normalize_tool_name(name))
    return names


def _precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return len(set(top_k) & relevant) / len(top_k)


def _r_cap_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Capped recall: hits@k / min(k, |relevant|).

    Reaches 1.0 when the top-k slots contain the maximum possible number of
    relevant docs. Avoids the recall@k ceiling problem when |relevant| > k.
    """
    if not relevant:
        return 0.0
    hits = len(set(retrieved[:k]) & relevant)
    return hits / min(k, len(relevant))


def _ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """NDCG@k with binary relevance.

    Self-normalizes against the ideal ranking truncated at k, so the metric
    reaches 1.0 when the top-k contains min(|relevant|, k) relevant docs in
    the top positions.
    """
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    dcg = sum(
        (1.0 if key in relevant else 0.0) / math.log2(rank + 1)
        for rank, key in enumerate(top_k, start=1)
    )
    n_ideal = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, n_ideal + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def _log_metrics(
    case_id: str,
    tool_names: list[str],
    search_queries: list[str],
    retrieved: list[str],
    expected: set[str],
    precision: float,
    r_cap: float,
    ndcg: float,
) -> None:
    if not RETRIEVAL_VERBOSE:
        return
    top_k = retrieved[:RETRIEVAL_K]
    hits = [key for key in top_k if key in expected]
    p_label = f"precision@{RETRIEVAL_K}"
    r_label = f"r_cap@{RETRIEVAL_K}"
    n_label = f"ndcg@{RETRIEVAL_K}"
    width = max(len(p_label), len(r_label), len(n_label))
    print(
        "\n".join(
            [
                f"[retrieval] case={case_id}",
                f"  tools={tool_names or ['<none>']}",
                f"  query={search_queries}",
                f"  expected={sorted(expected)}",
                f"  hits={hits}",
                f"  retrieved={top_k}",
                "  metrics:",
                f"    {p_label:<{width}}  {precision:.3f}",
                f"    {r_label:<{width}}  {r_cap:.3f}",
                f"    {n_label:<{width}}  {ndcg:.3f}",
            ]
        )
    )


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_retrieval(case: dict):
    result = agent_runner.run(case["input"], include_files=False)
    tool_names = _extract_tool_names(result.tool_calls)
    search_queries = _extract_search_queries(result.tool_calls)
    retrieved_keys = _extract_retrieved_keys(result.tool_calls)
    expected_keys = set(case["expected_keys"])

    # Negative cases: no relevant tickets exist. Either the agent skips
    # retrieval entirely (fine for clearly off-topic queries), or it searches
    # and the similarity cutoff filters everything out. Both are pass states.
    # Tracked in _results for the aggregate count, but with None metrics —
    # excluded from mean P/R_cap/NDCG calculations.
    if not expected_keys:
        assert not retrieved_keys, (
            f"Expected no retrieved tickets (no relevant tickets exist for "
            f"this query), but got {retrieved_keys}"
        )
        _results.append(
            {
                "case_id": case["id"],
                "category": _classify_case(case["id"]),
                "precision": None,
                "r_cap": None,
                "ndcg": None,
            }
        )
        return

    assert (
        EXPECTED_RETRIEVAL_TOOL in tool_names
    ), f"Expected retrieval tool '{EXPECTED_RETRIEVAL_TOOL}' not found in {tool_names}"

    precision = _precision_at_k(retrieved_keys, expected_keys, RETRIEVAL_K)
    r_cap = _r_cap_at_k(retrieved_keys, expected_keys, RETRIEVAL_K)
    ndcg = _ndcg_at_k(retrieved_keys, expected_keys, RETRIEVAL_K)

    _log_metrics(
        case["id"],
        tool_names,
        search_queries,
        retrieved_keys,
        expected_keys,
        precision,
        r_cap,
        ndcg,
    )

    _results.append(
        {
            "case_id": case["id"],
            "category": _classify_case(case["id"]),
            "precision": precision,
            "r_cap": r_cap,
            "ndcg": ndcg,
        }
    )

    top_k = retrieved_keys[:RETRIEVAL_K]
    hits = [k for k in top_k if k in expected_keys]
    reason_suffix = f"retrieved={top_k}, expected={sorted(expected_keys)}, hits={hits}"

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=", ".join(top_k) if top_k else "<none>",
        expected_output=", ".join(sorted(expected_keys)),
        retrieval_context=retrieved_keys or ["<none>"],
    )

    precision_metric = PrecomputedMetric(
        name=f"Precision@{RETRIEVAL_K}",
        score=precision,
        threshold=MIN_PRECISION_AT_K,
        reason=f"precision@{RETRIEVAL_K}={precision:.3f}; {reason_suffix}",
    )
    r_cap_metric = PrecomputedMetric(
        name=f"R_cap@{RETRIEVAL_K}",
        score=r_cap,
        threshold=MIN_R_CAP_AT_K,
        reason=f"r_cap@{RETRIEVAL_K}={r_cap:.3f}; {reason_suffix}",
    )
    ndcg_metric = PrecomputedMetric(
        name=f"NDCG@{RETRIEVAL_K}",
        score=ndcg,
        threshold=MIN_NDCG,
        reason=f"ndcg@{RETRIEVAL_K}={ndcg:.3f}; {reason_suffix}",
    )

    assert_test(test_case, [precision_metric, r_cap_metric, ndcg_metric])


def test_retrieval_aggregate():
    """Print aggregate metrics — overall total plus per-category breakdown.

    Categories isolate different retrieval challenges:
      - original:   baseline Norwegian phrasing
      - paraphrase: same gold, different surface form (robustness to phrasing)
      - english:    English query, Norwegian corpus (cross-lingual)
      - negative:   no relevant tickets (cutoff calibration; no IR metrics)

    Negative cases have no relevant docs, so they don't contribute to the
    P/R_cap/NDCG means. Their pass count is reported separately.
    """
    if not _results:
        pytest.skip("No retrieval results collected")

    scored = [r for r in _results if r["precision"] is not None]
    by_category: dict[str, list[dict]] = {}
    for r in _results:
        by_category.setdefault(r["category"], []).append(r)

    def _means(rows: list[dict]) -> tuple[float, float, float]:
        n = len(rows)
        return (
            sum(r["precision"] for r in rows) / n,
            sum(r["r_cap"] for r in rows) / n,
            sum(r["ndcg"] for r in rows) / n,
        )

    lines = [
        "",
        "=" * 60,
        f"  RETRIEVAL AGGREGATE ({len(_results)} cases)",
        "=" * 60,
    ]

    if scored:
        p, r_cap, ndcg = _means(scored)
        lines.extend(
            [
                f"  Mean Precision@{RETRIEVAL_K}: {p:.3f}",
                f"  Mean R_cap@{RETRIEVAL_K}:     {r_cap:.3f}",
                f"  Mean NDCG@{RETRIEVAL_K}:      {ndcg:.3f}",
                "",
                "  By category:",
            ]
        )

    for category in ("original", "paraphrase", "english", "negative"):
        rows = by_category.get(category, [])
        if not rows:
            continue
        if category == "negative":
            lines.append(
                f"    Negative ({len(rows)} cases): all passed "
                f"— skipped retrieval or cutoff filtered"
            )
            continue
        p, r_cap, ndcg = _means(rows)
        lines.extend(
            [
                f"    {category.capitalize()} ({len(rows)} cases)",
                f"      Mean Precision@{RETRIEVAL_K}: {p:.3f}",
                f"      Mean R_cap@{RETRIEVAL_K}:     {r_cap:.3f}",
                f"      Mean NDCG@{RETRIEVAL_K}:      {ndcg:.3f}",
            ]
        )

    lines.append("=" * 60)
    print("\n".join(lines))
