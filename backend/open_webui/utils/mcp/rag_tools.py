"""
RAG Tools Implementation

Imported by MCP server.
"""

import logging
import os
from open_webui.retrieval.utils import generate_embeddings
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient

# ==================== SETUP ======================

log = logging.getLogger(__name__)

RAG_AZURE_OPENAI_KEY = os.environ.get("RAG_AZURE_OPENAI_API_KEY")
RAG_AZURE_OPENAI_VERSION = os.environ.get("RAG_AZURE_OPENAI_API_VERSION")
RAG_AZURE_OPENAI_MODEL = os.environ.get("RAG_EMBEDDING_MODEL")
RAG_AZURE_OPENAI_BASE_URL = os.environ.get("RAG_AZURE_OPENAI_BASE_URL")

JIRA_COLLECTION = "jira_support_tickets"

# ==================== MCP TOOLS ====================


async def search_vector_db_for_similar_jira_tickets(
    search_text: str,
    top_k: int = 5,
) -> str:
    """
    Summary:

    Args:
        search_text (str): Natural language query to search for.
        top_k (int, optional): Number of results to return. Defaults to 5.

    Returns:

    """
    log.info(f"Performing vector search via pgvector for search-text: '{search_text}'")
    pgVectorClient = PgvectorClient()
    extra_params = {
        "key": RAG_AZURE_OPENAI_KEY,
        "azure_api_version": RAG_AZURE_OPENAI_VERSION,
        "url": RAG_AZURE_OPENAI_BASE_URL,
    }
    embedding = await generate_embeddings(
        engine="azure_openai",
        model=RAG_AZURE_OPENAI_MODEL,
        text=search_text,
        # prefix=None,
        **extra_params,
    )

    search_result = pgVectorClient.search(
        collection_name=JIRA_COLLECTION,
        vectors=[embedding],
        # filter=None,
        limit=top_k,
    )

    if not search_result or not search_result.ids or not search_result.ids[0]:
        log.info("No similar Jira tickets found.")
        return None
    else:
        log.info(
            f"Retrieved top {len(search_result.ids[0])} most relevant Jira tickets"
        )
        return search_result
