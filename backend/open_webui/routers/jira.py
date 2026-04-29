"""HTTP endpoints for JIRA sync and create_issue"""

import os
import json
import logging
from httpx import AsyncClient

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.retrieval.jira_tickets import fetch_jira_tickets
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient
from open_webui.retrieval.vector.main import VectorItem

from open_webui.models.files import Files
from open_webui.storage.provider import Storage
from open_webui.utils.auth import get_admin_user, get_verified_user

# from open_webui.utils.jira.helpers import embed_jira_tickets
from open_webui.utils.jira.formatters import (
    description_text_to_adf,
    format_jira_ticket_for_embedding,
)
from open_webui.retrieval.utils import generate_embeddings
from open_webui.models.oauth_sessions import OAuthSessions

from datetime import datetime, timedelta
import aiohttp


# =================================================================================
# SETUP
# =================================================================================

log = logging.getLogger(__name__)
router = APIRouter()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL")
OPENAI_API_VERSION = os.environ.get("RAG_AZURE_OPENAI_API_VERSION")

RAG_AZURE_OPENAI_KEY = os.environ.get("RAG_AZURE_OPENAI_API_KEY")
RAG_AZURE_OPENAI_VERSION = os.environ.get("RAG_AZURE_OPENAI_API_VERSION")
RAG_AZURE_OPENAI_MODEL = os.environ.get("RAG_EMBEDDING_MODEL")
RAG_AZURE_OPENAI_BASE_URL = os.environ.get("RAG_AZURE_OPENAI_BASE_URL")

JIRA_CLOUD_ID_ENV = os.environ.get("JIRA_CLOUD_ID")
JIRA_CREATE_ISSUE_PROJECT_KEY = os.environ.get("JIRA_CREATE_ISSUE_PROJECT_KEY", "TESTSUPP")
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
                    log.error(
                        f"JIRA token refresh failed: {resp.status} - {error_text}"
                    )
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
        new_token["expires_at"] = int(datetime.now().timestamp()) + int(
            new_token["expires_in"]
        )

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
    if datetime.now() + timedelta(minutes=5) >= datetime.fromtimestamp(
        session.expires_at
    ):
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
# AUTOFILL
# =================================================================================


class JiraAutofillForm(BaseModel):
    messages: list[dict]


@router.post("/autofill")
async def autofill_jira(
    form: JiraAutofillForm,
    user=Depends(get_verified_user),
) -> dict:
    """
    Given a conversation, call Azure OpenAI to suggest a Jira ticket title,
    description, and urgency (A/B/C).
    """
    system_prompt = (
        "You are an IT support ticket assistant. Given a conversation between a user "
        "and an AI support agent, generate a Jira ticket on behalf of the user.\n\n"
        "Write the ticket from the user's first-person perspective, as if the user "
        "is filing it themselves. Use 'I' and 'my' (e.g. 'I tried...', 'I expected...', "
        "'my screen shows...'). Do NOT use third-person phrasing like 'the user reports', "
        "'the user tried', or 'they encountered'. Only include information the user "
        "actually provided in the conversation — do not attribute the AI agent's "
        "suggestions or explanations to the user.\n\n"
        "Fields:\n"
        "- title: A concise summary of the issue (max 100 characters). Neutral phrasing "
        "is fine here (e.g. 'Cannot log in to Trace WMS') — no need for 'I' in the title.\n"
        "- description: A detailed description in first person, covering what I was "
        "trying to do, what I tried, what happened, and what I expected to happen.\n"
        "- urgency: One of 'A', 'B', or 'C' where:\n"
        "    A = Critical/blocking, major system failure or complete inability to work\n"
        "    B = Significant impact, workaround exists\n"
        "    C = Minor issue, question, or low-priority request\n"
        "- affected_components: The system component affected by the issue. "
        "Must be exactly one of: 'Trace OMS', 'Trace TMS', or 'Trace WMS'. "
        "Choose based on the context — OMS for order management, TMS for transport management, WMS for warehouse management.\n\n"
        "Respond with ONLY a valid JSON object with keys 'title', 'description', 'urgency', and 'affected_components'. No other text."
    )

    conversation = [{"role": "system", "content": system_prompt}]
    for m in form.messages:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            conversation.append({"role": m["role"], "content": m["content"]})

    url = f"{OPENAI_API_BASE_URL}/chat/completions?api-version={OPENAI_API_VERSION}"
    headers = {
        "api-key": OPENAI_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "messages": conversation,
        "temperature": 0.3,
        "max_tokens": 500,
    }

    try:
        async with AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, detail="Failed to parse AI response as JSON"
        )
    except Exception as e:
        log.error(f"Jira autofill failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))


# =================================================================================
# SYNC
# =================================================================================


async def _sync_jira_tickets(since: str | None = None):
    """Core sync logic: fetch tickets, deduplicate, embed, upsert. Used by endpoint and poller."""
    tickets = await fetch_jira_tickets(since=since)
    fetched_ids = {t["id"] for t in tickets}

    pgVectorClient = PgvectorClient()
    existing = pgVectorClient.get(collection_name=JIRA_COLLECTION)
    existing_ids = set(existing.ids[0]) if existing else set()

    new_tickets = [t for t in tickets if t["id"] not in existing_ids]

    # Only remove stale tickets on a full sync (no since filter)
    stale_ids = []
    if not since:
        stale_ids = list(existing_ids - fetched_ids)
        if stale_ids:
            pgVectorClient.delete(collection_name=JIRA_COLLECTION, ids=stale_ids)
            log.info(f"Deleted {len(stale_ids)} stale tickets from vector DB")

    JIRA_LAST_SYNCED_AT.value = datetime.now().isoformat()
    JIRA_LAST_SYNCED_AT.save()

    if not new_tickets:
        log.info("No new tickets to embed, vector DB is up to date")
        return 0

    texts = [format_jira_ticket_for_embedding(t) for t in new_tickets]
    metadata_list = [
        {
            "id": t["id"],
            "key": t["key"],
            "status": t["status"],
            "created": t["created"],
            "issue_type": t.get("issue_type", ""),
            "priority": t.get("priority", ""),
            "assignee": t.get("assignee", ""),
        }
        for t in new_tickets
    ]

    extra_params = {
        "key": RAG_AZURE_OPENAI_KEY,
        "azure_api_version": RAG_AZURE_OPENAI_VERSION,
        "url": RAG_AZURE_OPENAI_BASE_URL,
    }
    embeddings = await generate_embeddings(
        engine="azure_openai",
        model=RAG_AZURE_OPENAI_MODEL,
        text=texts,
        **extra_params,
    )

    vector_items = [
        {
            "id": meta["id"],
            "text": text,
            "vector": emb,
            "metadata": meta,
        }
        for emb, text, meta in zip(embeddings, texts, metadata_list)
    ]

    pgVectorClient.upsert(collection_name=JIRA_COLLECTION, items=vector_items)

    log.info(
        f"Synced JIRA tickets: {len(new_tickets)} embedded, "
        f"{len(stale_ids)} stale deleted, "
        f"{len(fetched_ids) - len(new_tickets)} unchanged"
    )
    return len(new_tickets)


@router.post("/sync")
async def sync_jira(
    request: Request,
    user=Depends(get_admin_user),
):
    log.debug(f"User {user.id} requested syncing of JIRA tickets")
    try:
        await _sync_jira_tickets()
    except Exception as e:
        log.exception(f"JIRA sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/wipe")
async def wipe_jira_collection(user=Depends(get_admin_user)):
    """Delete all Jira tickets from the vector DB so the next sync re-embeds everything."""
    pgVectorClient = PgvectorClient()
    pgVectorClient.delete_collection(JIRA_COLLECTION)

    JIRA_LAST_WIPED_AT.value = datetime.now().isoformat()
    JIRA_LAST_WIPED_AT.save()

    log.info(f"Wiped collection '{JIRA_COLLECTION}'")
    return {"status": "ok", "collection": JIRA_COLLECTION}


@router.get("/status")
async def jira_status(user=Depends(get_verified_user)):
    has = VECTOR_DB_CLIENT.has_collection(JIRA_COLLECTION)
    last_synced = JIRA_LAST_SYNCED_AT.value or None
    last_wiped = JIRA_LAST_WIPED_AT.value or None
    # If wiped after the last sync, consider it not synced
    if last_wiped and (not last_synced or last_wiped > last_synced):
        has = False
    return {
        "synced": has,
        "collection": JIRA_COLLECTION,
        "last_synced_at": last_synced,
        "last_wiped_at": last_wiped,
    }


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
            log.error(
                f"Failed to fetch project meta: {response.status_code}: {response.text}"
            )
            raise HTTPException(
                status_code=502,
                detail=f"Jira API {response.status_code}: {response.text}",
            )
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
    summary: str
    description: str
    priority: str
    due_date: str | None = None
    assignee: str | None = None
    issue_type: str = "Task"
    file_ids: list[str] = []


@router.post("/create")
async def create_issue(
    form: JiraCreateTicketForm,  # Body will be parsed into this Pydantic model
    request: Request,
    user=Depends(get_verified_user),
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
    project_key = JIRA_CREATE_ISSUE_PROJECT_KEY
    log.debug(
        f"User {user.id} requested Jira issue creation in {project_key}, summary: {form.summary}"
    )

    jira_session = await _get_jira_session(user.id)
    if not jira_session:
        raise HTTPException(
            status_code=401,
            detail="No JIRA OAuth session found. Please connect your JIRA account.",
        )

    oauth_access_token = jira_session.token.get("access_token")
    jira_base_url = _get_jira_base_url(jira_session)
    url = f"{jira_base_url}/rest/api/3/issue"

    # 2. Build headers
    headers = {
        "Authorization": f"Bearer {oauth_access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # 3. Build payload
    log.debug(f"Building payload")
    fields = {
        "project": {"key": project_key},
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

    # 4. Create the issue
    try:
        async with AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            body = response.text
            log.error(f"Jira API error {response.status_code}: {body}")
            raise HTTPException(
                status_code=502, detail=f"Jira API {response.status_code}: {body}"
            )

        result = response.json()
        issue_key = result.get("key")
        if not issue_key:
            raise HTTPException(
                status_code=502, detail="Jira issue created but no key returned"
            )
        log.info(f"Created Jira issue {issue_key} in project {project_key}")

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to create Jira issue: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    # 5. Attach files (separate API calls)
    attachment_results = {"attached": [], "failed": []}

    if form.file_ids:
        attach_url = f"{jira_base_url}/rest/api/3/issue/{issue_key}/attachments"
        attach_headers = {
            "Authorization": f"Bearer {oauth_access_token}",
            "X-Atlassian-Token": "no-check",
        }

        for file_id in form.file_ids:
            try:
                file_record = Files.get_file_by_id(file_id)
                if not file_record:
                    raise RuntimeError("File record not found")

                local_path = Storage.get_file(file_record.path)
                filename = (file_record.meta or {}).get("name", file_record.filename)

                with open(local_path, "rb") as f:
                    file_bytes = f.read()

                async with AsyncClient() as client:
                    resp = await client.post(
                        attach_url,
                        headers=attach_headers,
                        files={"file": (filename, file_bytes)},
                        timeout=60,
                    )

                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"Jira attachment API error {resp.status_code}: {resp.text}"
                    )

                attachment_results["attached"].append(
                    {"file_id": file_id, "filename": filename}
                )
                log.info(f"Attached {filename} to {issue_key}")

            except Exception as e:
                log.warning(f"Failed to attach file {file_id} to {issue_key}: {e}")
                attachment_results["failed"].append(
                    {"file_id": file_id, "error": str(e)}
                )

    if attachment_results["failed"]:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Issue created, but one or more attachments failed",
                "issue_key": issue_key,
                "attachments": attachment_results,
                "issue": result,
            },
        )

    return result
