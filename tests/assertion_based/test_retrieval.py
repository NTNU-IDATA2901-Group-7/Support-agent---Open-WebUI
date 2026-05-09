"""
Retrieval — assertion-based key-based retrieval evaluation.

Cases are defined in cases/retrieval.yaml.

Supports:
  - expected key labels
  - precision@k
  - recall@k
  - MRR

Thresholds are configured globally in this file to keep case authoring simple.
"""

import os
import re

import pytest

from tests.conftest import load_yaml
from tests.utils import agent_runner

CASES = load_yaml("retrieval.yaml")

_KEY_RE = re.compile(r"Key:\s*(\S+)")

RETRIEVAL_K = int(os.environ.get("RETRIEVAL_K", "5"))
MIN_PRECISION_AT_K = float(os.environ.get("MIN_PRECISION_AT_K", "0.2"))
MIN_RECALL_AT_K = float(os.environ.get("MIN_RECALL_AT_K", "0.5"))
MIN_MRR = float(os.environ.get("MIN_MRR", "0.5"))
RETRIEVAL_VERBOSE = os.environ.get("RETRIEVAL_VERBOSE", "1") == "1"
EXPECTED_RETRIEVAL_TOOL = "search_vector_db_for_similar_jira_tickets_tool"


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


def _recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def _mrr(retrieved: list[str], relevant: set[str]) -> float:
    for rank, key in enumerate(retrieved, start=1):
        if key in relevant:
            return 1.0 / rank
    return 0.0


def _log_metrics(
    case_id: str,
    tool_names: list[str],
    search_queries: list[str],
    retrieved: list[str],
    expected: set[str],
    precision_at_k: float,
    recall_at_k: float,
    mrr: float,
) -> None:
    if not RETRIEVAL_VERBOSE:
        return
    top_k = retrieved[:RETRIEVAL_K]
    hits = [key for key in top_k if key in expected]
    print(
        "\n".join(
            [
                f"[retrieval] case={case_id}",
                f"  tools={tool_names or ['<none>']}",
                f"  query={search_queries}",
                f"  expected={sorted(expected)}",
                f"  hits={hits}",
                f"  top_{RETRIEVAL_K}={top_k}",
                f"  all_retrieved={retrieved}",
                (
                    f"  metrics: precision@{RETRIEVAL_K}={precision_at_k:.3f}, "
                    f"recall@{RETRIEVAL_K}={recall_at_k:.3f}, mrr={mrr:.3f}"
                ),
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

    assert (
        EXPECTED_RETRIEVAL_TOOL in tool_names
    ), f"Expected retrieval tool '{EXPECTED_RETRIEVAL_TOOL}' not found in {tool_names}"

    actual_precision = _precision_at_k(retrieved_keys, expected_keys, RETRIEVAL_K)
    actual_recall = _recall_at_k(retrieved_keys, expected_keys, RETRIEVAL_K)
    actual_mrr = _mrr(retrieved_keys, expected_keys)

    _log_metrics(
        case["id"],
        tool_names,
        search_queries,
        retrieved_keys,
        expected_keys,
        actual_precision,
        actual_recall,
        actual_mrr,
    )

    # assert actual_precision >= MIN_PRECISION_AT_K, (
    #     f"precision@{RETRIEVAL_K}={actual_precision:.3f} < {MIN_PRECISION_AT_K:.3f}; "
    #     f"retrieved={retrieved_keys}, expected={sorted(expected_keys)}"
    # )
    assert actual_recall >= MIN_RECALL_AT_K, (
        f"recall@{RETRIEVAL_K}={actual_recall:.3f} < {MIN_RECALL_AT_K:.3f}; "
        f"retrieved={retrieved_keys}, expected={sorted(expected_keys)}"
    )
    assert actual_mrr >= MIN_MRR, (
        f"mrr={actual_mrr:.3f} < {MIN_MRR:.3f}; "
        f"retrieved={retrieved_keys}, expected={sorted(expected_keys)}"
    )
