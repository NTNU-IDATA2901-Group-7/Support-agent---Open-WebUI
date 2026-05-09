"""HTTP endpoints for JIRA operations"""

import os
import json
import logging
from httpx import AsyncClient

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.retrieval.jira_tickets import sync_jira_tickets, JIRA_LAST_SYNCED_AT
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient

from open_webui.models.files import Files
from open_webui.storage.provider import Storage
from open_webui.utils.auth import get_admin_user, get_verified_user

from open_webui.utils.jira.formatters import description_text_to_adf
from open_webui.utils.jira.oauth import get_jira_session, JIRA_OAUTH_BASE_URL
from open_webui.config import PersistentConfig

from datetime import datetime


# =================================================================================
# SETUP
# =================================================================================

log = logging.getLogger(__name__)
router = APIRouter()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL")
OPENAI_API_VERSION = os.environ.get("RAG_AZURE_OPENAI_API_VERSION")

JIRA_CREATE_ISSUE_PROJECT_KEY = os.environ.get(
    "JIRA_CREATE_ISSUE_PROJECT_KEY", "TESTSUPP"
)
JIRA_COLLECTION = "jira_support_tickets"

JIRA_LAST_WIPED_AT = PersistentConfig("JIRA_LAST_WIPED_AT", "jira.last_wiped_at", "")


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


@router.post("/sync")
async def sync_jira(
    request: Request,
    user=Depends(get_admin_user),
):
    log.debug(f"User {user.id} requested syncing of JIRA tickets")
    try:
        await sync_jira_tickets()
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
    jira_session = await get_jira_session(user.id)
    if not jira_session:
        raise HTTPException(status_code=401, detail="No JIRA OAuth session found.")

    oauth_access_token = jira_session.token.get("access_token")
    url = f"{JIRA_OAUTH_BASE_URL}/project/{project_key}"

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

    jira_session = await get_jira_session(user.id)
    if not jira_session:
        raise HTTPException(
            status_code=401,
            detail="No JIRA OAuth session found. Please connect your JIRA account.",
        )

    oauth_access_token = jira_session.token.get("access_token")
    url = f"{JIRA_OAUTH_BASE_URL}/issue"

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
    attachment_results = await _attach_files(
        issue_key, form.file_ids, oauth_access_token
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


async def _attach_files(issue_key: str, file_ids: list[str], access_token: str) -> dict:
    """Attach files to a Jira issue. Returns dict with 'attached' and 'failed' lists."""
    url = f"{JIRA_OAUTH_BASE_URL}/issue/{issue_key}/attachments"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Atlassian-Token": "no-check",
    }
    results = {"attached": [], "failed": []}

    for file_id in file_ids:
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
                    url,
                    headers=headers,
                    files={"file": (filename, file_bytes)},
                    timeout=60,
                )

            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Jira attachment API error {resp.status_code}: {resp.text}"
                )

            results["attached"].append({"file_id": file_id, "filename": filename})
            log.info(f"Attached {filename} to {issue_key}")

        except Exception as e:
            log.warning(f"Failed to attach file {file_id} to {issue_key}: {e}")
            results["failed"].append({"file_id": file_id, "error": str(e)})

    return results
