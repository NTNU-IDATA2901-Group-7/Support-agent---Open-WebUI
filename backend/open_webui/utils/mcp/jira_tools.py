import logging
from jira import JIRA
from jira.exceptions import JIRAError

log = logging.getLogger(__name__)

# Jira Credentials
domain = "driwno.atlassian.net"
email = "mathias.lovnes@solwr.com"
# TODO: Move this api_token to env file
api_token = "ATATT3xFfGF017g0QKBo_JY37lfkParjecVWpsYF7hJGM_8eIGxbY_gJq25qZi30dBdCV2mnPx0OacHYN0SaXbwD9ifzgcfmM4hVSCvNWpVVccTN_F0vdLuAwhj30ocMEKJJ3AE5hPirN3IY6TDQymsV-rPOYX5TJF5oLiKIa_bOeHElCMbyDAY=CE509555"
project_key = "TT"

jira_client = JIRA(
    server=f"https://{domain}",
    basic_auth=(email, api_token)
)


# TODO: Test if LLM can handle dynamic jql_query param or if it needs to be split into separate fields
def search_jira_tickets_by_jql(jql_query: str, maxResults: int = 10) -> dict[str, list[dict[str, str]]]:
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
    try:
        issues = jira_client.search_issues(jql_query, maxResults=maxResults)
    except JIRAError as e:
        log.exception(f"JQL request failed: {e.status_code} - {e.text}")
        raise RuntimeError(f"JQL request failed: {e.status_code}")

    if not issues:
        log.info(f"No tickets found matching that JQL: {jql_query}")
        return {"tickets": []}

    results = []
    for issue in issues:
        results.append({
            "id": issue.id,
            "key": issue.key,
            "summary": issue.fields.summary or "No summary",
            "description": issue.fields.description or "",
            "status": issue.fields.status.name or "Unknown status"
        })

    log.info(f"Found {len(results)} issues from JQL: '{jql_query}'")
    for r in results:
        log.debug(f"Issue: {r['key']} - {r['summary']} (Status: {r['status']})")

    return {"tickets": results}



# TODO: Add better logging
def get_jira_ticket_details_by_key(ticket_key: str) -> dict[str, dict[str, str]]:
    """
    Fetches the full details of a specific ticket.

    Args:
        issue_key (str): The Jira issue key (e.g., "TT-123").

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
    try:
        issue = jira_client.issue(ticket_key)
    except JIRAError as e:
        log.error(f"Failed to fetch ticket {ticket_key}: {e.status_code} - {e.text}")
        raise RuntimeError(f"Failed to fetch ticket {ticket_key}: {e.status_code}")

    fields = issue.fields

    assignee_obj = fields.assignee
    if assignee_obj:
        assignee_info = f"{assignee_obj.displayName} ({assignee_obj.emailAddress})"
    else:
        assignee_info = "Unassigned"
    
    result =  {
        "key": issue.key,
        "summary": fields.summary or "No summary",
        "description": fields.description or "",
        "status": getattr(fields.status, "name", "Unknown status"),
        "priority": getattr(fields.priority, "name", "None"),
        "assignee": assignee_info,
        "created": getattr(fields, "created", "Unknown")
    }

    return {"ticket": result}





# ------------------------------------------------------------------
# ---------------------- Methods for testing -----------------------

# --- search_by_jql ---
# testsupp_tickets = search_by_jql("project = TESTSUPP")
# print(testsupp_tickets)

# --- get_ticket_details ---
# print(get_ticket_details('TESTSUPP-25'))
