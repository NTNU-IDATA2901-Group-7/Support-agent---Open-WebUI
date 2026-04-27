"""
Support Agent MCP Server

MCP protocol layer that exposes all tools to Open-WebUI, and handles tool calls by routing to the
actual method implementations.

Runs as a Streamable HTTP server (default: http://0.0.0.0:8000/mcp).
"""

# TODO: Implement better error handling

import logging
import os
from typing import Annotated

from pydantic import Field
from mcp.server.fastmcp import FastMCP

# Import tool implementations
from open_webui.utils.mcp.jira_tools import (
    get_jira_ticket_details_by_key,
    search_jira_tickets_by_jql,
)
from open_webui.utils.mcp.rag_tools import (
    search_vector_db_for_similar_jira_tickets,
    # TODO: implement search_documentation
)

# Import formatters
from open_webui.utils.jira.formatters import (
    format_similar_jira_ticket_search_results,
    format_jira_ticket_details,
    format_jql_search_results,
)

# ============================================================================
# SETUP
# ============================================================================

log = logging.getLogger(__name__)

MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))
VECTOR_SEARCH_TOP_K = int(os.environ.get("VECTOR_SEARCH_TOP_K", "5"))
VECTOR_SEARCH_SIMILARITY_CUTOFF = float(
    os.environ.get("VECTOR_SEARCH_SIMILARITY_CUTOFF", "0.5")
)

server = FastMCP(
    "support-agent-tools",
    host=MCP_HOST,
    port=MCP_PORT,
)

# ============================================================================
# TOOL CATALOG - What the LLM sees
# ============================================================================

# ==================== JIRA TOOLS ====================


@server.tool()
async def search_jira_tickets_by_jql_tool(
    jql_query: str,
    maxResults: Annotated[int, Field(ge=1, le=100)] = 10,
) -> str:
    """
    Search Jira tickets using JQL (Jira Query Language) for precise filtering.

    When to use: User needs specific filtering by project, status, assignee, date, etc.
    Input: JQL query string (e.g., 'project = PROJ AND status = "Open"')
    Output: List of matching tickets with key, summary, description, and status.

    Use this for structured queries. For semantic/meaning-based search,
    use search_vector_db_for_similar_jira_tickets_tool instead.

    :param jql_query: JQL query string. Examples: 'project = SR AND status = "To Do"', 'assignee = currentUser() AND priority = High', 'created >= -7d ORDER BY created DESC'
    :param maxResults: Maximum number of tickets to return (1-20, default 10)
    """
    log.info(f"MCP Tool called: search_jira_tickets_by_jql")
    result = await search_jira_tickets_by_jql(
        jql_query=jql_query,
        maxResults=maxResults,
    )
    return format_jql_search_results(result)


@server.tool()
async def get_jira_ticket_details_by_key_tool(ticket_key: str) -> str:
    """
    Get full details of a specific Jira ticket by its key.

    When to use: User asks about a specific ticket (e.g., "What's the status of PROJ-123?")
    Input: Jira ticket key like "PROJ-123"
    Output: Full ticket details including description, status, assignee, etc.

    :param ticket_key: Jira ticket key (e.g., PROJ-123)
    """
    log.info(f"MCP Tool called: get_jira_ticket_details_by_key")
    result = await get_jira_ticket_details_by_key(
        ticket_key=ticket_key,
    )
    return format_jira_ticket_details(result)


# ==================== RAG TOOLS ====================


@server.tool()
async def search_vector_db_for_similar_jira_tickets_tool(
    search_text: str,
) -> str:
    """
    Search for Jira tickets semantically similar to a natural language query.

    When to use: User asks about existing tickets, bug reports, or similar issues.
    Input: Natural language description (e.g., "login button not working", "payment processing errors")
    Output: List of similar tickets with keys, summaries, status, and similarity scores.

    Retrieval parameters are fixed server-side to keep RAG evaluation stable.

    :param search_text: Natural language query describing what tickets to find
    """
    log.info(f"MCP Tool called: search_vector_db_for_similar_jira_tickets")
    result = await search_vector_db_for_similar_jira_tickets(
        search_text=search_text,
        top_k=VECTOR_SEARCH_TOP_K,
        similarity_cutoff=VECTOR_SEARCH_SIMILARITY_CUTOFF,
    )
    if result is None:
        return "No similar tickets found."
    return format_similar_jira_ticket_search_results(result)


# ============================================================================
# SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    log.info(f"Starting Support Agent MCP Server on {MCP_HOST}:{MCP_PORT}")
    server.run(transport="streamable-http")
