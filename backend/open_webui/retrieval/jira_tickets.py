"""
JIRA ticket fetching and embedding logic.
Importable by routers (HTTP trigger) or standalone scripts.
"""

import os
import logging
from markdownify import markdownify

from fastapi import HTTPException
from open_webui.utils.jira.client import jira_api_get

# =================================================================================
# SETUP
# =================================================================================

log = logging.getLogger(__name__)

JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY")

# =================================================================================
# FETCH JIRA TICKETS
# =================================================================================


async def fetch_jira_tickets(since: str | None = None) -> list[dict]:
    """
    Fetch Jira tickets for a given project and return as a list of dicts.
    If `since` is provided (ISO timestamp), only fetch tickets updated after that time.
    """
    jql = f"project = {JIRA_PROJECT_KEY} AND status = Closed"
    if since:
        # Jira JQL expects 'yyyy-MM-dd HH:mm' format
        jql += f' AND updated >= "{since[:16].replace("T", " ")}"'
    jql += " ORDER BY updated DESC"

    query = {
        "jql": jql,
        "maxResults": 100,
        "fields": "created,status,assignee,issuetype,priority,description,summary,key",
        "expand": "renderedFields",
    }

    log.info("Fetching jira tickets")
    try:
        jira_data = await jira_api_get("/search/jql", params=query)
    except Exception as e:
        log.error(f"Failed to fetch Jira tickets: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    log.info("Parsing fields of tickets JSONs.")
    tickets = []
    for issue in jira_data["issues"]:
        rendered_description = (issue.get("renderedFields") or {}).get(
            "description"
        ) or ""
        fields = issue["fields"]
        assignee_obj = fields.get("assignee")
        tickets.append(
            {
                "id": issue["id"],
                "key": issue["key"],
                "created": fields["created"],
                "status": fields["status"]["name"],
                "summary": fields["summary"],
                "description": (
                    markdownify(rendered_description) if rendered_description else ""
                ),
                "issue_type": (fields.get("issuetype") or {}).get("name", ""),
                "priority": (fields.get("priority") or {}).get("name", ""),
                "assignee": assignee_obj["displayName"] if assignee_obj else "",
            }
        )

    log.info(f"Fetched {len(tickets)} JIRA tickets")
    return tickets
