"""
JIRA ticket fetching, syncing, and embedding logic.
Importable by routers (HTTP trigger) or standalone scripts.
"""

import asyncio
import os
import logging
from datetime import datetime
from markdownify import markdownify

from fastapi import HTTPException
from open_webui.utils.jira.client import jira_api_get
from open_webui.utils.jira.formatters import format_jira_ticket_for_embedding
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient
from open_webui.retrieval.utils import generate_embeddings
from open_webui.config import PersistentConfig

# =================================================================================
# SETUP
# =================================================================================

log = logging.getLogger(__name__)

JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY")

RAG_AZURE_OPENAI_KEY = os.environ.get("RAG_AZURE_OPENAI_API_KEY")
RAG_AZURE_OPENAI_VERSION = os.environ.get("RAG_AZURE_OPENAI_API_VERSION")
RAG_AZURE_OPENAI_MODEL = os.environ.get("RAG_EMBEDDING_MODEL")
RAG_AZURE_OPENAI_BASE_URL = os.environ.get("RAG_AZURE_OPENAI_BASE_URL")

JIRA_COLLECTION = "jira_support_tickets"
JIRA_POLL_INTERVAL_SECONDS = 86400

JIRA_LAST_SYNCED_AT = PersistentConfig("JIRA_LAST_SYNCED_AT", "jira.last_synced_at", "")

# =================================================================================
# FETCH JIRA TICKETS
# =================================================================================


JIRA_TICKET_FETCH_LIMIT = 300
JIRA_PAGE_SIZE = 100  # /search/jql caps each response at 100 regardless of maxResults


async def fetch_jira_tickets(jql: str | None = None) -> list[dict]:
    """
    Fetch Jira tickets for the configured project and return as a list of dicts.

    Paginates using nextPageToken until JIRA_TICKET_FETCH_LIMIT is reached or no further pages remain.
    By default fetches the most recently updated tickets; pass a custom `jql` to override.
    """
    if jql is None:
        jql = f"project = {JIRA_PROJECT_KEY} ORDER BY updated DESC"

    log.info("Fetching jira tickets")
    tickets: list[dict] = []
    next_page_token: str | None = None

    while len(tickets) < JIRA_TICKET_FETCH_LIMIT:
        params = {
            "jql": jql,
            "maxResults": min(JIRA_PAGE_SIZE, JIRA_TICKET_FETCH_LIMIT - len(tickets)),
            "fields": "created,status,assignee,issuetype,priority,description,summary,key",
            "expand": "renderedFields",
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        try:
            jira_data = await jira_api_get("/search/jql", params=params)
        except Exception as e:
            log.error(f"Failed to fetch Jira tickets: {e}")
            raise HTTPException(status_code=502, detail=str(e))

        issues = jira_data.get("issues", [])
        if not issues:
            break

        for issue in issues:
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
                        markdownify(rendered_description)
                        if rendered_description
                        else ""
                    ),
                    "issue_type": (fields.get("issuetype") or {}).get("name", ""),
                    "priority": (fields.get("priority") or {}).get("name", ""),
                    "assignee": assignee_obj["displayName"] if assignee_obj else "",
                }
            )

        next_page_token = jira_data.get("nextPageToken")
        if not next_page_token:
            break

    log.info(f"Fetched {len(tickets)} JIRA tickets")
    return tickets


# =================================================================================
# SYNC & POLL
# =================================================================================


async def sync_jira_tickets(jql: str | None = None):
    """Core sync logic: fetch tickets, deduplicate, embed, upsert. Used by endpoint and poller."""
    tickets = await fetch_jira_tickets(jql=jql)
    fetched_ids = {t["id"] for t in tickets}

    pgVectorClient = PgvectorClient()
    existing = pgVectorClient.get(collection_name=JIRA_COLLECTION)

    # Build lookup of existing metadata and documents by ID
    existing_meta = {}
    existing_docs = {}
    if existing and existing.ids[0]:
        for i, eid in enumerate(existing.ids[0]):
            existing_meta[eid] = (
                existing.metadatas[0][i] if existing.metadatas[0] else {}
            )
            existing_docs[eid] = (
                existing.documents[0][i] if existing.documents[0] else ""
            )

    # Determine which tickets need (re-)embedding
    tickets_to_upsert = []
    for t in tickets:
        if (
            t["id"] not in existing_docs
            or format_jira_ticket_for_embedding(t) != existing_docs[t["id"]]
        ):
            tickets_to_upsert.append(t)

    JIRA_LAST_SYNCED_AT.value = datetime.now().isoformat()
    JIRA_LAST_SYNCED_AT.save()

    if not tickets_to_upsert:
        log.info("No new or updated tickets to embed, vector DB is up to date")
        return 0

    texts = [format_jira_ticket_for_embedding(t) for t in tickets_to_upsert]
    metadata_list = []
    for t in tickets_to_upsert:
        meta = {
            "id": t["id"],
            "key": t["key"],
            "status": t["status"],
            "created": t["created"],
            "issue_type": t["issue_type"],
            "priority": t["priority"],
            "assignee": t["assignee"],
        }
        # Preserve cached solution/comment_count from RAG retrieval
        old = existing_meta.get(t["id"], {})
        if old.get("solution"):
            meta["solution"] = old["solution"]
        if "comment_count" in old:
            meta["comment_count"] = old["comment_count"]
        metadata_list.append(meta)

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
        f"Synced JIRA tickets: {len(tickets_to_upsert)} upserted, "
        f"{len(fetched_ids) - len(tickets_to_upsert)} unchanged"
    )
    return len(tickets_to_upsert)


async def poll_jira_loop():
    """Background loop: periodically reconcile the vector DB against Jira."""
    log.info(f"Jira polling started (interval: {JIRA_POLL_INTERVAL_SECONDS}s)")
    while True:
        await asyncio.sleep(JIRA_POLL_INTERVAL_SECONDS)
        try:
            count = await sync_jira_tickets()
            if count:
                log.info(f"Jira poll: embedded {count} new tickets")
            else:
                log.debug("Jira poll: no new tickets")
        except Exception as e:
            log.error(f"Jira poll failed: {e}")
