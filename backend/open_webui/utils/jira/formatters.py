"""
RESULT FORMATTERS - Converts data to LLM-readable text
"""

import logging

log = logging.getLogger(__name__)


# ==================== JIRA FORMATTERS ====================


def description_text_to_adf(description: str) -> dict:
    """Convert plain description text to ADF (Atlassian Document Format) - used by create_issue
    method"""
    return {
        "content": [
            {"content": [{"text": description, "type": "text"}], "type": "paragraph"}
        ],
        "type": "doc",
        "version": 1,
    }


def format_similar_jira_ticket_search_results(result) -> str:
    """
    Formats Jira tickets search result into a structured text block for LLM context.
    Args:
        search_result (SearchResult): Output from vector search.
    Returns:
        str: Formatted text
    """
    num = len(result.ids[0])
    log.info(f"Formatting Jira ticket search results ({num} results)")

    rows = zip(
        result.ids[0],
        result.documents[0],
        result.metadatas[0],
        result.distances[0],
    )

    lines = [f"Top {num} most relevant Jira tickets:\n"]
    for i, (doc_id, doc_text, meta, score) in enumerate(rows, 1):
        lines.append(f"[{i}]")
        lines.append(f"Key: {meta.get('key', doc_id)}")
        lines.append(
            f"Summary: {meta.get('summary', doc_text[:80] if doc_text else '')}"
        )
        lines.append(f"Similarity: {score:.2f}\n")
    str_result = "\n".join(lines)
    log.debug(str_result)
    return str_result


def format_jira_ticket_details(ticket_dict: dict) -> str:
    """
    Format the output of `get_jira_ticket_details_by_key` into a readable
    block for LLM context.

    Args:
        ticket_dict (dict): Dictionary returned by `get_jira_ticket_details_by_key`.

    Returns:
        str: Formatted text block
    """
    ticket = ticket_dict.get("ticket")
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

    log.info("Finished formatting Jira ticket details")
    return "\n".join(lines)


def format_jira_ticket_for_embedding(ticket: dict) -> str:
    """
    Format a ticket into a format fit for embedding them as vectors.

    Args:
        ticket (dict): The ticket (with summary and description fields) you want to embed.

    Returns:
        str: The ticket with summary and description formatted.
    """
    lines = [
        f"Summary: {ticket.get('summary', '')}",
        f"Description: {ticket.get('description', '')}",
        f"Key: {ticket.get('key', '')}",
        f"Status: {ticket.get('status', '')}",
        f"Type: {ticket.get('issue_type', '')}",
        f"Priority: {ticket.get('priority', '')}",
        f"Assignee: {ticket.get('assignee', '')}",
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
