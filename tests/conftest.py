"""
Shared fixtures and configuration for the test suite.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
import yaml

CASES = Path(__file__).parent / "cases"
REPO_ROOT = Path(__file__).parent.parent


# ── Hyperparameter helpers (Confident AI / DeepEval) ─────────────

AGENT_MODEL = "Azure gpt-4.1-mini"
JUDGE_MODEL = "Azure gpt-4.1-mini"
SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()


def _extract_function_docstring(file_path: Path, function_name: str) -> str:
    """Read a function's docstring without importing the module.

    Used to surface tool descriptions (e.g. the vector-search tool) as a
    tracked prompt in Confident AI without pulling in heavy backend deps
    (torch, sentence_transformers) at test collection time.
    """
    tree = ast.parse(file_path.read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ):
            return ast.get_docstring(node) or ""
    raise ValueError(f"Function {function_name!r} not found in {file_path}")


SEARCH_TOOL_DESCRIPTION = _extract_function_docstring(
    REPO_ROOT / "backend/open_webui/utils/mcp/rag_tools.py",
    "search_vector_db_for_similar_jira_tickets",
)


def common_hyperparameters() -> dict:
    """Hyperparameters that apply to every LLM-judge test suite."""
    return {
        "agent_model": AGENT_MODEL,
        "judge_model": JUDGE_MODEL,
    }


def rag_hyperparameters() -> dict:
    """RAG-specific hyperparameters. Only relevant for suites whose outcome
    depends on retrieval."""
    return {
        "rag_embedding_model": os.getenv(
            "RAG_EMBEDDING_MODEL", "text-embedding-3-large"
        ),
        "rag_reranking_model": os.getenv(
            "RAG_RERANKING_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ),
        "rag_top_k": os.getenv("RAG_TOP_K", "10"),
        "rag_top_k_reranker": os.getenv("RAG_TOP_K_RERANKER", "5"),
        "rag_hybrid_bm25_weight": os.getenv("RAG_HYBRID_BM25_WEIGHT", "0.25"),
        "rag_use_reranker": os.getenv("RAG_USE_RERANKER", "true"),
    }


def tool_hyperparameters() -> dict:
    """Tool-related hyperparameters. Only relevant for suites where the agent
    invokes tools (retrieval, and any LLM-judge suite that exercises RAG)."""
    return {
        "search_tool_description": SEARCH_TOOL_DESCRIPTION,
    }


# ── Fixtures ─────────────────────────────────────────────────────


def load_yaml(filename: str) -> list[dict]:
    """Load a YAML file from the test/cases/ directory and return the list of test cases.

    Test files call this to load their ground-truth data, e.g. load_yaml("docs_correctness.yaml").
    Each YAML file contains a list of dicts with fields like id, input, expected_output, etc.
    """
    path = CASES / filename
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session", autouse=True)
def teardown_agent_client():
    """Session-scoped fixture that cleans up the agent_runner's HTTP client.

    Runs automatically (autouse=True) for the entire test session. The yield
    lets all tests run first, then agent_runner.close() fires once at the end
    to release the httpx connection used to talk to Open WebUI.

    Only imports agent_runner if it was actually used (i.e., llm_judge tests ran).
    Deterministic tests skip this entirely.
    """
    yield
    try:
        from tests.utils import agent_runner

        agent_runner.close()
    except ImportError:
        pass


# ── Markers ──────────────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "assertion_based: assertion-based tests (no LLM judge)"
    )
    config.addinivalue_line(
        "markers", "llm_judge: LLM-as-judge tests (costs API tokens)"
    )


def pytest_collection_modifyitems(items):
    """Auto-tag tests with markers based on their directory.

    Tests under test/llm_judge/   get @pytest.mark.llm_judge
    Tests under test/assertion_based/ get @pytest.mark.assertion_based

    This lets us run subsets selectively:
        pytest -m assertion_based   # fast smoke tests, no LLM calls
        pytest -m llm_judge         # slow tests scored by DeepEval, costs API tokens
    """
    for item in items:
        path = str(item.fspath)
        if "llm_judge" in path:
            item.add_marker(pytest.mark.llm_judge)
        if "assertion_based" in path:
            item.add_marker(pytest.mark.assertion_based)
