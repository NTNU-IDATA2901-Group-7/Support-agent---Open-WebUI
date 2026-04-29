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
    similarity_cutoff: float = 0.5,
):
    """
    Search for Jira tickets semantically similar to the query.

    Args:
        search_text (str): Natural language query to search for.
        top_k (int, optional): Maximum number of results to return. Defaults to 5.
        similarity_cutoff (float, optional): Minimum similarity score. Results below
            this threshold are filtered out. Defaults to 0.5.

    Returns:
        SearchResult with results above the cutoff, or None if no matches.
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

    # Filter out results below the similarity cutoff
    keep = []
    for i, score in enumerate(search_result.distances[0]):
        if score >= similarity_cutoff:
            keep.append(i)

    if not keep:
        log.info(f"All results below similarity cutoff {similarity_cutoff}.")
        return None

    search_result.ids[0] = [search_result.ids[0][i] for i in keep]
    search_result.documents[0] = [search_result.documents[0][i] for i in keep]
    search_result.metadatas[0] = [search_result.metadatas[0][i] for i in keep]
    search_result.distances[0] = [search_result.distances[0][i] for i in keep]

    log.info(f"Retrieved {len(keep)} Jira tickets above cutoff {similarity_cutoff}")
    for rank, i in enumerate(keep, 1):
        key = search_result.metadatas[0][rank - 1].get("key", search_result.ids[0][rank - 1])
        score = search_result.distances[0][rank - 1]
        log.info(f"  #{rank}  {key}  (similarity: {score:.4f})")
    return search_result
