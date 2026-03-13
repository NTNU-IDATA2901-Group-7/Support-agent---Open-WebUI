
"""HTTP endpoints for JIRA sync and create_issue"""

import os
import logging
from httpx import AsyncClient

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.retrieval.jira_tickets import fetch_jira_tickets
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient
from open_webui.retrieval.vector.main import VectorItem

from open_webui.utils.auth import get_admin_user, get_verified_user
# from open_webui.utils.jira.helpers import embed_jira_tickets
from open_webui.utils.jira.formatters import description_text_to_adf, format_jira_ticket_for_embedding
from open_webui.utils.embeddings import generate_embeddings
from open_webui.models.oauth_sessions import OAuthSessions

from datetime import datetime, timedelta
import aiohttp


# =================================================================================
# SETUP
# =================================================================================

log = logging.getLogger(__name__)
router = APIRouter()

JIRA_CLOUD_ID_ENV = os.environ.get("JIRA_CLOUD_ID")
JIRA_COLLECTION = "jira_support_tickets"
JIRA_OAUTH_PROVIDER = "atlassian"
ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_CLIENT_ID = os.environ.get("ATLASSIAN_CLIENT_ID", "")
ATLASSIAN_CLIENT_SECRET = os.environ.get("ATLASSIAN_CLIENT_SECRET", "")


async def _refresh_jira_token(session) -> dict | None:
    """Refresh an expired Atlassian OAuth token, preserving custom metadata."""
    token_data = session.token
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        log.warning(f"No refresh token for JIRA session {session.id}")
        return None

    refresh_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": ATLASSIAN_CLIENT_ID,
        "client_secret": ATLASSIAN_CLIENT_SECRET,
    }
    try:
        async with aiohttp.ClientSession(trust_env=True) as http:
            async with http.post(
                ATLASSIAN_TOKEN_URL,
                json=refresh_data,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log.error(f"JIRA token refresh failed: {resp.status} - {error_text}")
                    return None
                new_token = await resp.json()
    except Exception as e:
        log.error(f"JIRA token refresh exception: {e}")
        return None

    # Preserve refresh_token if the provider didn't return a new one
    if "refresh_token" not in new_token:
        new_token["refresh_token"] = refresh_token

    # Preserve custom metadata stored during initial OAuth
    for key in ("cloud_id", "atlassian_account_id"):
        if key not in new_token and key in token_data:
            new_token[key] = token_data[key]

    new_token["issued_at"] = int(datetime.now().timestamp())
    if "expires_in" in new_token and "expires_at" not in new_token:
        new_token["expires_at"] = int(datetime.now().timestamp()) + int(new_token["expires_in"])

    updated = OAuthSessions.update_session_by_id(session.id, new_token)
    if updated:
        log.info(f"Refreshed JIRA token for session {session.id}")
        return updated.token
    return None


async def _get_jira_session(user_id: str):
    """
    Get a valid Atlassian OAuthSession for the user,
    refreshing automatically if close to expiry.

    Returns the OAuthSessionModel or None.
    """
    session = OAuthSessions.get_session_by_provider_and_user_id(
        JIRA_OAUTH_PROVIDER, user_id
    )
    if not session:
        log.warning(f"No JIRA OAuth session for user {user_id}")
        return None

    # Refresh if expiring within 5 minutes
    if datetime.now() + timedelta(minutes=5) >= datetime.fromtimestamp(session.expires_at):
        log.debug(f"JIRA token near expiry for user {user_id}, refreshing")
        refreshed = await _refresh_jira_token(session)
        if refreshed:
            # Re-fetch the updated session
            session = OAuthSessions.get_session_by_provider_and_user_id(
                JIRA_OAUTH_PROVIDER, user_id
            )
            if session:
                return session
        # Refresh failed – delete stale session
        OAuthSessions.delete_session_by_id(session.id)
        log.warning(f"JIRA token refresh failed for user {user_id}, session deleted")
        return None

    return session


def _get_jira_base_url(session) -> str:
    """Build the JIRA API base URL from the session's cloud_id or env fallback."""
    cloud_id = session.token.get("cloud_id") or JIRA_CLOUD_ID_ENV
    if not cloud_id:
        raise HTTPException(
            status_code=500,
            detail="No Jira cloud_id found. Please reconnect your Atlassian account.",
        )
    return f"https://api.atlassian.com/ex/jira/{cloud_id}"


# =================================================================================
# SYNC
# =================================================================================

# TODO: Test, and add documentation and detailed logging
@router.post("/sync")
async def sync_jira(
    request: Request,
    user=Depends(get_admin_user),
):
    log.debug(f"User {user.id} requested syncing of JIRA tickets")
    jira_session = await _get_jira_session(user.id)
    if not jira_session:
        raise HTTPException(status_code=401, detail="No JIRA OAuth session found. Please connect your JIRA account.")

    oauth_access_token = jira_session.token.get("access_token")

    try:
        tickets = await fetch_jira_tickets(oauth_access_token)

        texts = [format_jira_ticket_for_embedding(ticket) for ticket in tickets]
        metadata_list = [
            {
                "id": ticket["id"],
                "key": ticket["key"],
                "status": ticket["status"],
                "created": ticket["created"]
            } for ticket in tickets
        ]

        embedding_input = {
            "model": "text-embedding-ada-002",
            "input": texts,
        }

        embedding_response = await generate_embeddings(request=request, form_data=embedding_input, user=user)

        vector_items = [
            VectorItem(
                id=meta["id"],
                text=text,
                vector=emb["embedding"],
                metadata=meta
            )
            for emb, text, meta in zip(embedding_response["data"], texts, metadata_list)
        ]

        # Lazily initialize pgVectorClient only when needed
        pgVectorClient = PgvectorClient()
        pgVectorClient.upsert(collection_name=JIRA_COLLECTION, items=vector_items)
        log.info('Successfully synced jira tickets with vector database')
    except Exception as e:
        log.exception(f"JIRA sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# TODO: Add when it was last synced - timestamp needs to be passed when upserting collection
@router.get("/status")
async def jira_status(user=Depends(get_verified_user)):
    has = VECTOR_DB_CLIENT.has_collection(JIRA_COLLECTION)
    return {"synced": has, "collection": JIRA_COLLECTION}





# =================================================================================
# PROJECT METADATA (issue types)
# =================================================================================

@router.get("/project-meta/{project_key}")
async def get_project_meta(
    project_key: str,
    user=Depends(get_verified_user),
) -> dict:
    """Return available issue types for a JIRA project."""
    jira_session = await _get_jira_session(user.id)
    if not jira_session:
        raise HTTPException(status_code=401, detail="No JIRA OAuth session found.")

    oauth_access_token = jira_session.token.get("access_token")
    jira_base_url = _get_jira_base_url(jira_session)
    url = f"{jira_base_url}/rest/api/3/project/{project_key}"

    headers = {
        "Authorization": f"Bearer {oauth_access_token}",
        "Accept": "application/json",
    }

    try:
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            log.error(f"Failed to fetch project meta: {response.status_code}: {response.text}")
            raise HTTPException(status_code=502, detail=f"Jira API {response.status_code}: {response.text}")
        data = response.json()
        issue_types = [
            {"id": it["id"], "name": it["name"], "subtask": it.get("subtask", False)}
            for it in data.get("issueTypes", [])
        ]
        return {"project_key": project_key, "issue_types": issue_types}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching project meta: {e}")
        raise HTTPException(status_code=502, detail=str(e))


# =================================================================================
# CREATE ISSUE
# =================================================================================

class JiraCreateTicketForm(BaseModel):
    project_key: str
    summary: str
    description: str
    priority: str
    due_date: str | None = None
    assignee: str | None = None
    issue_type: str = "Task"


@router.post("/create")
async def create_issue(
    form: JiraCreateTicketForm, # Body will be parsed into this Pydantic model
    request: Request,
    user = Depends(get_verified_user)
) -> dict:
    """
    Create a Jira issue in a given project.

    Args:
        project_key (str): The key of the Jira project (e.g., "TEST").
        summary (str): Title/summary of the issue.
        description (str): Plain text description/body of the issue.
        priority (str): Priority level, e.g., "A", "B", or "C".
        due_date (str): Due date for the issue, in YYYY-MM-DD format (default None).
        assignee (str): Account ID to assign the issue to (default None).
        issue_type (str, optional): Type of Jira issue (default "Task").

    Returns:
        The JSON response from Jira API (created issue info), and None if it fails to create the
    issue.
    """
    log.debug(f"User {user.id} requested Jira issue creation in {form.project_key}, summary: {form.summary}")

    jira_session = await _get_jira_session(user.id)
    if not jira_session:
        raise HTTPException(status_code=401, detail="No JIRA OAuth session found. Please connect your JIRA account.")

    oauth_access_token = jira_session.token.get("access_token")
    jira_base_url = _get_jira_base_url(jira_session)
    url = f"{jira_base_url}/rest/api/3/issue"

    # 2. Build headers
    headers = {
        "Authorization": f"Bearer {oauth_access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # 3. Build payload
    log.debug(f"Building payload")
    fields = {
        "project": {"key": form.project_key},
        "summary": form.summary,
        "description": description_text_to_adf(form.description),
        "priority": {"name": form.priority},
        "issuetype": {"name": form.issue_type},
    }

    if form.due_date:
        fields["duedate"] = form.due_date
    if form.assignee:
        fields["assignee"] = {"id": form.assignee}

    payload = {"fields": fields}
    log.debug(f"Payload built: {payload}")

    # 4. Post to Jira
    try:
        async with AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            body = response.text
            log.error(f"Jira API error {response.status_code}: {body}")
            raise HTTPException(status_code=502, detail=f"Jira API {response.status_code}: {body}")
        log.info(f"Created Jira issue {response.json().get('key')} in project {form.project_key}")
        return response.json()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to create Jira issue: {e}")
        raise HTTPException(status_code=502, detail=str(e))

