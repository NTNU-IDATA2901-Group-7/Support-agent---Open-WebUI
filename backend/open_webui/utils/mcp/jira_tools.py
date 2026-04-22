import os
import logging
from base64 import b64encode
from httpx import AsyncClient
from markdownify import markdownify

log = logging.getLogger(__name__)

JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY")
JIRA_SERVICE_ACCOUNT_EMAIL = os.environ.get("JIRA_SERVICE_ACCOUNT_EMAIL")
JIRA_SERVICE_ACCOUNT_API_TOKEN = os.environ.get("JIRA_SERVICE_ACCOUNT_API_TOKEN")

BASE_URL = os.environ.get("JIRA_API_BASE_URL")

_basic_credentials = b64encode(
    f"{JIRA_SERVICE_ACCOUNT_EMAIL}:{JIRA_SERVICE_ACCOUNT_API_TOKEN}".encode()
).decode()


async def search_jira_tickets_by_jql(
    jql_query: str, maxResults: int = 10
) -> dict[str, list[dict[str, str]]]:
    """
    Runs a Jira Query Language (JQL) search and returns a structured list of tickets.

    This function searches for issues matching the given JQL query.
    Each ticket includes key fields such as id, key, summary, description, and status.
    If no tickets are found, it returns an empty list under the "tickets" key.

    Args:
        jql_query (str): The JQL string to filter issues (e.g.,
                         'project = TT AND status = "To Do"').
        maxResults (int, optional): Maximum number of issues to return. Defaults to 10.

    Returns:
        dict[str, list[dict[str, str]]]: A dictionary with a single key "tickets",
            whose value is a list of dictionaries. Each dictionary represents a ticket
            with the following keys:
                - id (int): The numeric ID of the ticket.
                - key (str): The Jira issue key (e.g., "TT-123").
                - summary (str): The summary/title of the ticket.
                - description (str): The description text of the ticket.
                - status (str): The current status of the ticket (e.g., "To Do").

    Raises:
        RuntimeError: If the JQL request fails (e.g., network issue, bad authentication).
    """
    log.info(f"Searching Jira with JQL: '{jql_query}' (maxResults={maxResults})")
    headers = {
        "Authorization": f"Basic {_basic_credentials}",
        "Accept": "application/json",
    }
    params = {
        "jql": jql_query,
        "maxResults": maxResults,
        "fields": "summary,description,status",
        "expand": "renderedFields",
    }
    try:
        async with AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/search/jql", headers=headers, params=params
            )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.exception(f"JQL request failed: {e}")
        raise RuntimeError(f"JQL request failed: {e}")

    issues = data.get("issues", [])
    if not issues:
        log.info(f"No tickets found matching JQL: {jql_query}")
        return {"tickets": []}

    results = []
    for issue in issues:
        rendered_description = (issue.get("renderedFields") or {}).get(
            "description"
        ) or ""
        results.append(
            {
                "id": issue["id"],
                "key": issue["key"],
                "summary": issue["fields"].get("summary") or "No summary",
                "description": (
                    markdownify(rendered_description) if rendered_description else ""
                ),
                "status": (issue["fields"].get("status") or {}).get("name")
                or "Unknown status",
            }
        )

    log.info(f"Found {len(results)} issues from JQL: '{jql_query}'")
    for r in results:
        log.debug(f"Issue: {r['key']} - {r['summary']} (Status: {r['status']})")

    return {"tickets": results}


async def get_jira_ticket_details_by_key(ticket_key: str) -> dict[str, dict[str, str]]:
    """
    Fetches the full details of a specific ticket.

    Args:
        ticket_key (str): The Jira issue key (e.g., "TT-123").

    Returns:
        dict[str, str]: A dictionary with detailed ticket info:
            - key (str): The Jira issue key (e.g., "TT-123").
            - summary (str): The summary/title of the ticket.
            - description (str): The description text of the ticket.
            - status (str): The current status of the ticket (e.g., "To Do").
            - priority (str): The priority of the ticket (e.g., "High", "Medium").
            - assignee (str): Name and email of the assigned user, or "Unassigned".
            - created (str): Timestamp when the ticket was created.

    Raises:
        RuntimeError: If the ticket cannot be fetched.
    """
    log.info(f"Fetching Jira ticket: {ticket_key}")
    headers = {
        "Authorization": f"Basic {_basic_credentials}",
        "Accept": "application/json",
    }
    try:
        async with AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/issue/{ticket_key}",
                headers=headers,
                params={"expand": "renderedFields"},
            )
        response.raise_for_status()
        issue = response.json()
    except Exception as e:
        log.error(f"Failed to fetch ticket {ticket_key}: {e}")
        raise RuntimeError(f"Failed to fetch ticket {ticket_key}: {e}")

    fields = issue["fields"]
    rendered_description = (issue.get("renderedFields") or {}).get("description") or ""

    assignee_obj = fields.get("assignee")
    if assignee_obj:
        assignee_info = (
            f"{assignee_obj['displayName']} ({assignee_obj.get('emailAddress', '')})"
        )
    else:
        assignee_info = "Unassigned"

    log.info(
        f"Fetched ticket {ticket_key}: '{fields.get('summary')}' (Status: {(fields.get('status') or {}).get('name')})"
    )

    return {
        "ticket": {
            "key": issue["key"],
            "summary": fields.get("summary") or "No summary",
            "description": (
                markdownify(rendered_description) if rendered_description else ""
            ),
            "status": (fields.get("status") or {}).get("name") or "Unknown status",
            "priority": (fields.get("priority") or {}).get("name") or "None",
            "assignee": assignee_info,
            "created": fields.get("created") or "Unknown",
        }
    }
