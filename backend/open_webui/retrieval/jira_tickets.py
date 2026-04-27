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


async def fetch_jira_tickets() -> list[dict]:
    """
    Fetch all Jira tickets for a given project and return as a list of dicts.
    """
    query = {
        "jql": f"project = {JIRA_PROJECT_KEY} AND status = Closed ORDER BY updated DESC",
        "maxResults": 20,
        "fields": "created,status,assignee,type,status,description,summary,key",
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
        tickets.append(
            {
                "id": issue["id"],
                "key": issue["key"],
                "created": issue["fields"]["created"],
                "status": issue["fields"]["status"]["name"],
                "summary": issue["fields"]["summary"],
                "description": (
                    markdownify(rendered_description) if rendered_description else ""
                ),
            }
        )

    log.info(f"Fetched {len(tickets)} JIRA tickets")
    return tickets
