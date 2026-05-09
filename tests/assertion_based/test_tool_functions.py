"""
Direct tests for MCP tool functions — bypasses the MCP protocol layer.

These call the Python functions directly and assert on the returned data
structures (dicts/lists), not formatted strings. Catches issues like
empty results, missing fields, or bad auth that MCP-level tests can't
distinguish from "no results found".

Run with:  pytest -m assertion_based
"""

import asyncio
import os

import pytest

from open_webui.utils.mcp.jira_tools import (
    search_jira_tickets_by_jql,
    get_jira_ticket_details_by_key,
)
from open_webui.utils.mcp.rag_tools import (
    search_vector_db_for_similar_jira_tickets,
)


def run(coro):
    """Run an async function synchronously."""
    return asyncio.run(coro)


# ── JQL Search ────────────────────────────────────────────���──────


def test_jql_search_returns_tickets():
    """JQL search should return a dict with a non-empty 'tickets' list."""
    jql = f"project = {os.environ.get('JIRA_PROJECT_KEY')} ORDER BY created DESC"
    result = run(search_jira_tickets_by_jql(jql, maxResults=5))

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "tickets" in result, f"Missing 'tickets' key, got keys: {result.keys()}"
    assert len(result["tickets"]) > 0, "JQL search returned 0 tickets"


def test_jql_search_ticket_has_required_fields():
    """Each ticket from JQL search should have key, summary, status."""
    jql = f"project = {os.environ.get('JIRA_PROJECT_KEY')} ORDER BY created DESC"
    result = run(search_jira_tickets_by_jql(jql, maxResults=1))

    ticket = result["tickets"][0]
    for field in ("key", "summary", "status"):
        assert field in ticket, f"Ticket missing '{field}' field"


# ── Ticket Lookup ────────────────────────────────────────────────


def test_ticket_lookup_returns_ticket():
    """Ticket lookup should return a dict with a 'ticket' key."""
    ticket_key = os.environ.get("TEST_TICKET_KEY")
    result = run(get_jira_ticket_details_by_key(ticket_key))

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "ticket" in result, f"Missing 'ticket' key, got keys: {result.keys()}"


def test_ticket_lookup_has_required_fields():
    """Ticket details should include key, summary, status, priority, assignee, created."""
    ticket_key = os.environ.get("TEST_TICKET_KEY")
    result = run(get_jira_ticket_details_by_key(ticket_key))

    ticket = result["ticket"]
    for field in ("key", "summary", "status", "priority", "assignee", "created"):
        assert field in ticket, f"Ticket missing '{field}' field"
    assert (
        ticket["key"] == ticket_key
    ), f"Expected key '{ticket_key}', got '{ticket['key']}'"


# ── Vector Search ────────────────────────────────────────────────


def test_vector_search_returns_results():
    """Vector search should return a SearchResult with at least one match."""
    result = run(search_vector_db_for_similar_jira_tickets("login issue", top_k=3))

    assert result is not None, "Vector search returned None (no matches)"
    assert result.ids is not None, "SearchResult.ids is None"
    assert len(result.ids[0]) > 0, "Vector search returned 0 results"


def test_vector_search_result_has_required_fields():
    """Each result should have an id, document text, metadata, and distance score."""
    result = run(search_vector_db_for_similar_jira_tickets("login issue", top_k=1))

    assert len(result.ids[0]) == 1, "Expected exactly 1 result"
    assert len(result.documents[0]) == 1, "Missing document text"
    assert len(result.metadatas[0]) == 1, "Missing metadata"
    assert len(result.distances[0]) == 1, "Missing distance score"
