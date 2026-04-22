"""
JIRA ticket fetching and embedding logic.

Importable by routers (HTTP trigger) or standalone scripts.
"""

import os
import logging
from httpx import AsyncClient
from markdownify import markdownify

from fastapi import HTTPException

# =================================================================================
# SETUP
# =================================================================================

log = logging.getLogger(__name__)
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY")

BASE_URL = os.environ.get("JIRA_API_BASE_URL")

# =================================================================================
# FETCH JIRA TICKETS
# =================================================================================


async def fetch_jira_tickets(oauth_access_token: str) -> list[dict]:
    """
    Fetch all Jira tickets for a given project and return as a list of dicts.

    ARGS:
        oauth_access_token: the OAuth access token needed to make the GET request to jira.
    """
    # 1. Build headers
    headers = {
        "Authorization": f"Bearer {oauth_access_token}",
        "Accept": "application/json",
    }

    # 2. Create a URL and a query that matches all tickets
    url = f"{BASE_URL}/search/jql"
    query = {
        "jql": f"project = {JIRA_PROJECT_KEY} ORDER BY created DESC",
        "fields": "created,status,assignee,type,status,description,summary,key",
        "expand": "renderedFields",
    }

    # 3. GET the tickets from Jira
    log.info("Fetching jira tickets")
    tickets = []
    try:
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers, params=query)
        jira_data = response.json()
    except Exception as e:
        log.error(f"Failed to fetch Jira tickets: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    log.info("Parsing fields of tickets JSONs.")
    # 4. Transform Jira format into our "tickets" list format
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
