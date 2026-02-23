"""HTTP endpoint for JIRA sync"""

import os
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.retrieval.jira_tickets import fetch_jira_tickets
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient
from open_webui.retrieval.vector.main import VectorItem

from open_webui.utils.auth import get_admin_user, get_verified_user
# from open_webui.utils.jira.helpers import embed_jira_tickets
from open_webui.utils.jira.formatters import format_jira_ticket_for_embedding
from open_webui.utils.embeddings import generate_embeddings


# =================================================================================
# SETUP
# =================================================================================

log = logging.getLogger(__name__)
router = APIRouter()
pgVectorClient = PgvectorClient()

JIRA_CLOUD_ID = os.environ.get("JIRA_CLOUD_ID")
JIRA_COLLECTION = "jira_support_tickets"
JIRA_BASE_URL = f"https://api.atlassian.com/ex/jira/{JIRA_CLOUD_ID}"
JIRA_OAUTH_PROVIDER = os.environ.get("JIRA_OAUTH_PROVIDER")

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
    # 1. Get OAuth token from Open WebUI's built-in OAuth client manager
    oauth_client_manager = request.app.state.oauth_client_manager
    oauth_token_dict = await oauth_client_manager.get_oauth_token(
        user_id=user.id,
        client_id=JIRA_OAUTH_PROVIDER,
        force_refresh=False
    )

    oauth_access_token = oauth_token_dict.get("access_token")

    if not oauth_access_token:
        log.warning(f"No valid JIRA OAuth token found for user_id {user.id}, client_id {JIRA_OAUTH_PROVIDER}")
        raise HTTPException(status_code=401, detail="No JIRA OAuth session found")

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


