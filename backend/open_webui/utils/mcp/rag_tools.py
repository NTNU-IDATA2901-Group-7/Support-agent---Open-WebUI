import logging
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer('all-MiniLM-L6-v2')
log = logging.getLogger(__name__)

def search_vector_db_for_similar_jira_tickets(
        query_text: str,
        collection_name: str = "jira_collection",
        limit: int = 3
    ) -> dict[str, list[dict[str, str | float]]]:
    """
    Searches a Qdrant collection for Jira tickets semantically similar to the query text.

    Args:
        query_text (str): Natural language query to search for.
        collection_name (str, optional): Name of the Qdrant collection. Defaults to "jira_collection".
        limit (int, optional): Maximum number of results to return. Defaults to 3.

    Returns:
        dict[str, list[dict[str, str | float]]]: Dictionary with a single key "results",
            containing a list of results. Each result is a dict with:
                - key (str): Jira issue key.
                - summary (str): Issue summary.
                - score (float): Similarity score from Qdrant.
                - payload (dict): Full payload stored in Qdrant.
    """
    log.info(f"Performing vector search for query text: '{query_text}'")

    # Convert the user's question into a vector
    query_vector = model.encode(query_text).tolist()

    try:
        # Search Qdrant
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
        ).points

    except Exception as e:
        log.exception(f"Vector search failed: {e}")
        raise RuntimeError("Vector search failed")

    # Format results
    formatted = []
    for res in results:
        payload = res.payload or {}
        formatted.append({
            "key": payload.get("key", "Unknown"),
            "summary": payload.get("summary", ""),
            "score": res.score,
            "payload": payload
        })

    log.info(f"Vector search returned top {len(formatted)} results")

    for r in formatted:
        log.debug(f"Result: {r['key']} | score={r['score']:.4f} - {r['summary']}")

    return {"results": formatted}




# ------------------------------------------------------------------
# ---------------------- Methods for testing -----------------------

# --- search_vector_db_for_similar_jira_tickets ---
# print(search_vector_db_for_similar_jira_tickets('Develop new botton')) # test
