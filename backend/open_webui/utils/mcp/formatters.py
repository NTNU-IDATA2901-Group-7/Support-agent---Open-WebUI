"""
RESULT FORMATTERS - Converts data to LLM-readable text
"""

import logging
log = logging.getLogger(__name__)

# ==================== JIRA FORMATTERS ====================

def format_similar_jira_ticket_search_results(result: dict) -> str:
    """
    Formats Jira search results into a structured text block optimized for LLM context.

    Args:
        result (dict): Output from search_vector_db_for_similar_jira_tickets

    Returns:
        str: Formatted text block
    """
    results = result.get("results", [])
    log.info(f"Formatting Jira ticket search results ({len(results)} results)")

    if not results:
        return "Relevant Jira tickets:\n\nNo similar tickets found."

    lines = [f"Top {len(results)} most relevant Jira tickets:\n"]

    for i, r in enumerate(results, 1):
        key = r.get("key", "Unknown")
        summary = r.get("summary", "")
        score = r.get("score", 0.0)

        lines.append(f"[{i}]")
        lines.append(f"Key: {key}")
        lines.append(f"Summary: {summary}")
        lines.append(f"Similarity: {score:.2f}")
        lines.append("")

    log.info("Finished formatting Jira ticket search results")
    return "\n".join(lines)


def format_jira_ticket_details(result: dict) -> str:
    """
    Format the output of `get_jira_ticket_details_by_key` into a readable
    block for LLM context.

    Args:
        result (dict): Dictionary returned by `get_jira_ticket_details_by_key`.

    Returns:
        str: Formatted text block
    """
    ticket = result.get("ticket")
    if not ticket:
        return "No ticket details found."

    lines = [
        f"Key: {ticket.get('key', 'Unknown')}",
        f"Summary: {ticket.get('summary', 'No summary')}",
        f"Status: {ticket.get('status', 'Unknown status')}",
        f"Priority: {ticket.get('priority', 'None')}",
        f"Assignee: {ticket.get('assignee', 'Unassigned')}",
        f"Created: {ticket.get('created', 'Unknown')}",
        f"Description: {ticket.get('description', '')}",
    ]

    return "\n".join(lines)


# ==================== RAG FORMATTERS ====================

def format_jql_search_results(result: dict) -> str:
    """
    Format JQL search results into readable text for LLM or display.

    Args:
        result (dict): The dictionary returned by `search_jira_tickets_by_jql`.

    Returns:
        str: A nicely formatted string listing each ticket with key, summary,
             status, and the full description.
    """
    tickets = result.get("tickets", [])

    if not tickets:
        return "No tickets found matching the JQL query."

    lines = [f"Found {len(tickets)} ticket(s):\n"]

    for i, ticket in enumerate(tickets, 1):
        lines.append(
            f"[{i}] Key: {ticket['key']}\n"
            f"Summary: {ticket['summary']}\n"
            f"Status: {ticket['status']}"
        )

        # Full description if available
        if ticket.get("description"):
            desc = ticket["description"].strip()
            if desc:
                lines.append(f"Description: {desc}")

        # Blank line between tickets
        lines.append("")

    return "\n".join(lines)



