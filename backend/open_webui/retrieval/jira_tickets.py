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
JIRA_POLL_INTERVAL_SECONDS = 300

JIRA_LAST_SYNCED_AT = PersistentConfig(
    "JIRA_LAST_SYNCED_AT", "jira.last_synced_at", ""
)

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


# =================================================================================
# SYNC & POLL
# =================================================================================


async def sync_jira_tickets(since: str | None = None):
    """Core sync logic: fetch tickets, deduplicate, embed, upsert. Used by endpoint and poller."""
    tickets = await fetch_jira_tickets(since=since)
    fetched_ids = {t["id"] for t in tickets}

    pgVectorClient = PgvectorClient()
    existing = pgVectorClient.get(collection_name=JIRA_COLLECTION)

    # Build lookup of existing metadata and documents by ID
    existing_meta = {}
    existing_docs = {}
    if existing and existing.ids[0]:
        for i, eid in enumerate(existing.ids[0]):
            existing_meta[eid] = existing.metadatas[0][i] if existing.metadatas[0] else {}
            existing_docs[eid] = existing.documents[0][i] if existing.documents[0] else ""

    # Determine which tickets need (re-)embedding
    tickets_to_upsert = []
    for t in tickets:
        if t["id"] not in existing_docs or format_jira_ticket_for_embedding(t) != existing_docs[t["id"]]:
            tickets_to_upsert.append(t)

    # Only remove stale tickets on a full sync (no since filter)
    stale_ids = []
    if not since:
        stale_ids = list(set(existing_docs.keys()) - fetched_ids)
        if stale_ids:
            pgVectorClient.delete(collection_name=JIRA_COLLECTION, ids=stale_ids)
            log.info(f"Deleted {len(stale_ids)} stale tickets from vector DB")

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
        f"{len(stale_ids)} stale deleted, "
        f"{len(fetched_ids) - len(tickets_to_upsert)} unchanged"
    )
    return len(tickets_to_upsert)


async def poll_jira_loop():
    """Background loop: periodically fetch recently closed tickets and upsert them."""
    log.info(f"Jira polling started (interval: {JIRA_POLL_INTERVAL_SECONDS}s)")
    while True:
        await asyncio.sleep(JIRA_POLL_INTERVAL_SECONDS)
        try:
            since = JIRA_LAST_SYNCED_AT.value or None
            count = await sync_jira_tickets(since=since)
            if count:
                log.info(f"Jira poll: embedded {count} new tickets")
            else:
                log.debug("Jira poll: no new tickets")
        except Exception as e:
            log.error(f"Jira poll failed: {e}")
