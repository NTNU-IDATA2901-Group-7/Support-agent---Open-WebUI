"""
Support Agent MCP Server

MCP protocol layer that exposes all tools to Open-WebUI, and handles tool calls by routing to the
actual method implementations.
"""

# TODO: Implement better error handling

import asyncio
import logging
from typing import Any

# MCP imports
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Import tool implementations
from jira_tools import (
    get_jira_ticket_details_by_key,
    search_jira_tickets_by_jql,
)
from rag_tools import (
    search_vector_db_for_similar_jira_tickets
    # TODO: implement search_documentation
)

# Import formatters
from formatters import (
    format_similar_jira_ticket_search_results,
    format_jira_ticket_details,
    format_jql_search_results,
)

# ============================================================================
# SETUP
# ============================================================================

log = logging.getLogger(__name__)
server = Server("support-agent-tools")

# ============================================================================
# TOOL CATALOG - What the LLM sees
# ============================================================================

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    Define all available tools.
    The LLM reads these descriptions to decide which tool to use.
    """
    return [
        # ==================== JIRA TOOLS ====================

        Tool(
            name="search_jira_tickets_by_jql",
            description="""
            Search Jira tickets using JQL (Jira Query Language) for precise filtering.

            **When to use:** User needs specific filtering by project, status, assignee, date, etc.
            **Input:** JQL query string (e.g., 'project = PROJ AND status = "Open"')
            **Output:** List of matching tickets with key, summary, description, and status.

            Use this for structured queries. For semantic/meaning-based search, use search_vector_db_for_similar_jira_tickets instead.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "jql_query": {
                        "type": "string",
                        "description": (
                            "JQL query string. Examples: "
                            "'project = TT AND status = \"To Do\"', "
                            "'assignee = currentUser() AND priority = High', "
                            "'created >= -7d ORDER BY created DESC'"
                        )
                    },
                    "maxResults": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["jql_query"]
            }
        ),

        Tool(
            name="get_jira_ticket_details_by_key",
            description="""
            Get full details of a specific Jira ticket by its key.

            **When to use:** User asks about a specific ticket (e.g., "What's the status of PROJ-123?")
            **Input:** Jira ticket key like "PROJ-123"
            **Output:** Full ticket details including description, status, assignee, etc.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_key": {
                        "type": "string",
                        "description": "Jira ticket key (e.g., PROJ-123)"
                    }
                },
                "required": ["ticket_key"]
            }
        ),

        # ==================== RAG TOOLS ====================

        Tool(
        name="search_vector_db_for_similar_jira_tickets",
        description="""
        Search for Jira tickets semantically similar to a natural language query.

        **When to use:** User asks about existing tickets, bug reports, or similar issues.
        **Input:** Natural language description (e.g., "login button not working", "payment processing errors")
        **Output:** List of similar tickets with keys, summaries, status, and similarity scores.

        Results are filtered by similarity_cutoff to ensure relevance.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "search_text": {
                        "type": "string",
                        "description": "Natural language query describing what tickets to find"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "similarity_cutoff": {
                        "type": "number",
                        "description": "Minimum similarity score (0.0-1.0). Higher = stricter matching.",
                        "default": 0.5,
                        "minimum": 0.0,
                        "maximum": 1.0
                    }
                },
                "required": ["search_text"]
            }
        ),]


# ============================================================================
# TOOL EXECUTION ROUTER
# ============================================================================

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Route tool calls to implementations and format results.
    """

    log.info(f"🔧 MCP Tool called: {name}")
    log.debug(f"Arguments for MCP tools {name}: {arguments}")

    try:
        # ==================== JIRA TOOLS ====================

        if name == "get_jira_ticket_details_by_key":
            result = await get_jira_ticket_details_by_key(
                ticket_key=arguments["ticket_key"]
            )
            return [TextContent(
                type="text",
                text=format_jira_ticket_details(result))]

        elif name == "search_jira_tickets_by_jql":
            result = await search_jira_tickets_by_jql(
                jql_query=arguments["jql_query"],
                maxResults=arguments.get("maxResults", 10)
            )
            return [TextContent(
                type="text",
                text=format_jql_search_results(result)
            )]

        # ==================== RAG TOOLS ====================

        elif name == "search_vector_db_for_similar_jira_tickets":
            result = search_vector_db_for_similar_jira_tickets(
                search_text=arguments["search_text"],
                top_k=arguments.get("top_k", 5),
                similarity_cutoff=arguments.get("similarity_cutoff", 0.5)
            )
            return [TextContent(
                type="text",
                text=format_similar_jira_ticket_search_results(result)
        )]

        # ==================== ERROR HANDLING ====================

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        log.exception(f"Error executing {name}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ============================================================================
# SERVER STARTUP
# ============================================================================

async def main():
    """Start the MCP server"""
    log.info("🚀 Starting Support Agent MCP Server...")
    log.info("📡 Waiting for connections from Open-WebUI...")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        # create_initialization_options() handles initialization automatically
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
