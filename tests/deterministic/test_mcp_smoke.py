"""
Smoke tests for the MCP server and its tools.

These are deterministic tests — no LLM involved, no DeepEval scoring.
They verify that the MCP server is reachable and each tool returns data.

Run with:  pytest -m deterministic

Uses the MCP Python SDK client to talk to the server. The MCP protocol
requires an initialization handshake before tools can be listed or called,
so plain HTTP requests won't work — we need the real client.
"""

import asyncio
import os

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")

EXPECTED_TOOLS = {
    "search_jira_tickets_by_jql_tool",
    "get_jira_ticket_details_by_key_tool",
    "search_vector_db_for_similar_jira_tickets_tool",
}


# ── Helper ───────────────────────────────────────────────────────


async def _run_mcp(callback):
    """Connect to the MCP server, run the callback with the session, then disconnect.

    Each test gets its own short-lived connection. The callback receives
    a ClientSession that's already initialized and ready to use.
    """
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await callback(session)


def run_mcp(callback):
    """Sync wrapper — runs the async MCP call in a fresh event loop."""
    return asyncio.run(_run_mcp(callback))


# ── Tests ────────────────────────────────────────────────────────


def test_server_lists_all_tools():
    """The MCP server should expose exactly the 3 expected tools."""

    async def _check(session: ClientSession):
        result = await session.list_tools()
        return {tool.name for tool in result.tools}

    tool_names = run_mcp(_check)
    assert tool_names == EXPECTED_TOOLS, f"Expected {EXPECTED_TOOLS}, got {tool_names}"


def test_vector_search_executes():
    """Semantic search tool runs without error."""

    async def _check(session: ClientSession):
        result = await session.call_tool(
            "search_vector_db_for_similar_jira_tickets_tool",
            {"search_text": "login issue"},
        )
        return result

    result = run_mcp(_check)
    assert not result.isError, f"Tool returned error: {result.content}"


def test_jql_search_executes():
    """JQL search tool runs without error."""
    jql = f"project = {os.environ.get('JIRA_PROJECT_KEY')} ORDER BY created DESC"

    async def _check(session: ClientSession):
        result = await session.call_tool(
            "search_jira_tickets_by_jql_tool",
            {"jql_query": jql, "maxResults": 5},
        )
        return result

    result = run_mcp(_check)
    assert not result.isError, f"Tool returned error: {result.content}"


def test_ticket_lookup_by_key():
    """Fetching a specific ticket by key should return its details."""
    ticket_key = os.environ.get("TEST_TICKET_KEY")

    async def _check(session: ClientSession):
        result = await session.call_tool(
            "get_jira_ticket_details_by_key_tool",
            {"ticket_key": ticket_key},
        )
        return result

    result = run_mcp(_check)
    assert not result.isError, f"Tool returned error: {result.content}"
    assert len(result.content) > 0, f"Ticket lookup for {ticket_key} returned empty"
