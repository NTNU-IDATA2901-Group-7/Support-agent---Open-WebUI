"""
RAG Tools Implementation

Imported by MCP server.
"""

import asyncio
import logging
import os
from httpx import AsyncClient
from open_webui.retrieval.utils import generate_embeddings, query_doc_with_hybrid_search
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient, DocumentChunk
from open_webui.retrieval.vector.main import SearchResult
from open_webui.utils.mcp.jira_tools import get_jira_ticket_comments
from open_webui.utils.jira.client import jira_api_get

import sentence_transformers
import torch

# ==================== SETUP ======================

log = logging.getLogger(__name__)

RAG_AZURE_OPENAI_KEY = os.environ.get("RAG_AZURE_OPENAI_API_KEY")
RAG_AZURE_OPENAI_VERSION = os.environ.get("RAG_AZURE_OPENAI_API_VERSION")
RAG_AZURE_OPENAI_MODEL = os.environ.get("RAG_EMBEDDING_MODEL")
RAG_AZURE_OPENAI_BASE_URL = os.environ.get("RAG_AZURE_OPENAI_BASE_URL")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "10"))
RAG_TOP_K_RERANKER = int(os.environ.get("RAG_TOP_K_RERANKER", "3"))
RAG_HYBRID_BM25_WEIGHT = float(os.environ.get("RAG_HYBRID_BM25_WEIGHT", "0.5"))
RAG_SIMILARITY_CUTOFF = float(os.environ.get("RAG_SIMILARITY_CUTOFF", "0.5"))

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL")
OPENAI_API_VERSION = os.environ.get("RAG_AZURE_OPENAI_API_VERSION")

JIRA_COLLECTION = "jira_support_tickets"

RAG_RERANKING_MODEL = os.environ.get(
    "RAG_RERANKING_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

_reranker = None


def _get_reranking_function():
    """Lazily load the cross-encoder reranking model."""
    global _reranker
    if _reranker is None:
        log.info(f"Loading reranking model: {RAG_RERANKING_MODEL}")
        cross_encoder = sentence_transformers.CrossEncoder(
            RAG_RERANKING_MODEL,
            activation_fn=torch.nn.Sigmoid(),
        )
        _reranker = lambda query, documents, user=None: cross_encoder.predict(
            [(query, doc.page_content) for doc in documents]
        )
    return _reranker


async def _summarize_comments(
    ticket_key: str, summary: str, comments: list[dict]
) -> str:
    """Use the LLM to extract a concise solution summary from a ticket's comment thread."""
    comment_text = "\n".join(
        f"{c['author']}: {c['body']}" for c in comments if c.get("body")
    )
    prompt = (
        f"Below is the comment thread for Jira ticket {ticket_key} "
        f"(Summary: {summary}).\n\n"
        f"{comment_text}\n\n"
        "Extract ONLY the solution or resolution from these comments. "
        "The audience is logistics staff at grocery chains (REMA, SPAR, KIWI etc.), not developers. "
        "Skip technical details like SQL, code, Kubernetes, deployments, etc. "
        "Focus on what the problem was, what caused it, and how it was resolved. "
        "If no solution was found, say 'No resolution found.'"
    )

    url = f"{OPENAI_API_BASE_URL}/chat/completions?api-version={OPENAI_API_VERSION}"
    headers = {"api-key": OPENAI_API_KEY, "Content-Type": "application/json"}
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    try:
        async with AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.warning(f"Failed to summarize comments for {ticket_key}: {e}")
        return "Could not summarize solution."


# ==================== MCP TOOLS ====================


async def search_vector_db_for_similar_jira_tickets(
    search_text: str,
    top_k: int = RAG_TOP_K,
    top_k_reranker: int = RAG_TOP_K_RERANKER,
    similarity_cutoff: float = RAG_SIMILARITY_CUTOFF,
):
    """
    Search for Jira tickets semantically similar to the query using hybrid search
    (BM25 keyword matching + vector similarity).

    Args:
        search_text (str): Natural language query to search for.
        top_k (int, optional): Initial BM25/vector candidate pool size before reranking.
        top_k_reranker (int, optional): Number of results to keep after reranking.
        similarity_cutoff (float, optional): Minimum similarity score. Results below
            this threshold are filtered out.

    Returns:
        SearchResult with results above the cutoff, or None if no matches.
    """
    log.info(f"Performing hybrid search for: '{search_text}'")
    log.info(
        f"RAG_HYBRID_BM25_WEIGHT={RAG_HYBRID_BM25_WEIGHT}, RAG_TOP_K={RAG_TOP_K}, RAG_TOP_K_RERANKER={RAG_TOP_K_RERANKER}, RAG_SIMILARITY_CUTOFF={RAG_SIMILARITY_CUTOFF}, RAG_RERANKING_MODEL={RAG_RERANKING_MODEL}"
    )
    pgVectorClient = PgvectorClient()
    extra_params = {
        "key": RAG_AZURE_OPENAI_KEY,
        "azure_api_version": RAG_AZURE_OPENAI_VERSION,
        "url": RAG_AZURE_OPENAI_BASE_URL,
    }

    async def embedding_function(text, prefix=None):
        return await generate_embeddings(
            engine="azure_openai",
            model=RAG_AZURE_OPENAI_MODEL,
            text=text,
            **extra_params,
        )

    # Fetch all documents from the collection for BM25 scoring
    collection_result = pgVectorClient.get(collection_name=JIRA_COLLECTION)
    if (
        not collection_result
        or not collection_result.documents
        or not collection_result.documents[0]
    ):
        log.info("No Jira tickets in collection.")
        return None

    result = await query_doc_with_hybrid_search(
        collection_name=JIRA_COLLECTION,
        collection_result=collection_result,
        query=search_text,
        embedding_function=embedding_function,
        k=top_k,
        reranking_function=_get_reranking_function(),
        k_reranker=top_k_reranker,
        r=similarity_cutoff,
        hybrid_bm25_weight=RAG_HYBRID_BM25_WEIGHT,
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    if not documents:
        log.info("No similar Jira tickets found.")
        return None

    # Extract IDs from metadata
    ids = [meta.get("id", "") for meta in metadatas]

    log.info(f"Retrieved {len(ids)} Jira tickets above cutoff {similarity_cutoff}")
    for rank, (meta, score) in enumerate(zip(metadatas, distances), 1):
        key = meta.get("key", ids[rank - 1] if rank - 1 < len(ids) else "?")
        log.info(f"  #{rank}  {key}  (score: {score:.4f})")

    # Fetch and summarize comments, with caching in DB metadata
    async def _fetch_and_summarize(meta, doc_text):
        key = meta.get("key")
        ticket_id = meta.get("id")
        if not key:
            return

        try:
            # Check current comment count (maxResults=0 fetches no bodies, just the total)
            count_data = await jira_api_get(
                f"/issue/{key}/comment", params={"maxResults": 0}
            )
            current_count = count_data.get("total", 0)  # default 0 if field missing
            cached_count = meta.get(
                "comment_count", -1
            )  # -1 = no cache yet (avoids false hit on 0-comment tickets)

            # Cache hit: solution exists and comment count unchanged
            if meta.get("solution") and current_count == cached_count:
                log.info(f"Using cached solution for {key}")
                return

            # Cache miss: fetch comments, summarize, persist
            comments_result = await get_jira_ticket_comments(key)
            comments = comments_result.get("comments", [])
            if comments:
                summary = doc_text.split("\n")[0]
                meta["solution"] = await _summarize_comments(key, summary, comments)
            else:
                meta["solution"] = "No comments found."
            meta["comment_count"] = current_count

            # Write back to DB so next retrieval is instant
            chunk = (
                pgVectorClient.session.query(DocumentChunk)
                .filter(DocumentChunk.id == ticket_id)
                .first()
            )
            if chunk:
                chunk.vmetadata["solution"] = meta["solution"]
                chunk.vmetadata["comment_count"] = current_count
                pgVectorClient.session.commit()
                log.info(f"Cached solution for {key} ({current_count} comments)")
        except Exception as e:
            log.warning(f"Failed to fetch/summarize comments for {key}: {e}")

    await asyncio.gather(
        *[
            _fetch_and_summarize(meta, doc_text)
            for meta, doc_text in zip(metadatas, documents)
        ]
    )

    search_result = SearchResult(
        ids=[ids],
        documents=[documents],
        metadatas=[metadatas],
        distances=[distances],
    )

    return search_result
