import logging
from llama_index.core import VectorStoreIndex
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

# ------------------------------------------------------------------
# ---------------------- Setup -------------------------------------

log = logging.getLogger(__name__)

# Setup Qdrant client
qdrant_client = QdrantClient(host="localhost", port=6333)
vector_store = QdrantVectorStore(
    qdrant_client=qdrant_client,
    collection_name="jira_collection",
)


# Initialize an index - a "wrapper" around the vector store - can generate retriever, query engines
# etc.
index = VectorStoreIndex.from_vector_store(vector_store)

# ------------------------------------------------------------------
# ---------------------- MCP Tools ---------------------------------

# TODO:
# Add LLM ReRank: https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/node_postprocessors/#llm-rerank
# Test similarity_cutoff
def search_vector_db_for_similar_jira_tickets(
        search_text: str,
        top_k: int = 5,
        similarity_cutoff: float = 0.5,
    ) -> dict[str, list[dict[str, str | float]]]:
    """
    Uses LlamaIndex to search a Qdrant collection for Jira tickets semantically similar to the
    search-text.

    Args:
        search_text (str): Natural language query to search for.
        top_k (int, optional): Number of results to return. Defaults to 5.
        similarity_cutoff (float, optional): The threshold at which search results are discarded.

    Returns:
        dict[str, list[dict[str, str | float]]]: Dictionary with a single key "results",
            containing a list of results. Each result is a dict with:
                - key (str): Jira issue key.
                - summary (str): Issue summary.
                - score (float): Similarity score from Qdrant.
                - payload (dict): Full payload stored in Qdrant.
    """
    log.info(f"Performing vector search via LlamaIndex for search-text: '{search_text}'")

    # Initialize retriever index - fetches top_k results
    retriever = index.as_retriever(similarity_top_k=top_k, similarity_cutoff=0.5)

    # Search Qdrant
    try:
        # Retrieve results
        results = retriever.retrieve(search_text)
        # Apply similarity cutoff filter
        if similarity_cutoff > 0:
            postprocessor = SimilarityPostprocessor(similarity_cutoff=similarity_cutoff)
            results = postprocessor.postprocess_nodes(results)
    except Exception as e:
        log.exception(f"Vector search failed: {e}")
        raise RuntimeError("Vector search failed")

    # Format results
    formatted = []
    for res in results:
        """metadata: key, summary, status, assignee etc - the fields entered when upserting the vectors to the vector DB"""
        metadata = res.node.metadata or {} 
        formatted.append({
            "score": res.score,
            **metadata, # ** to flatten the metadata object
        })

    log.info(f"Vector search returned top {len(formatted)} results")

    for r in formatted:
        log.debug(f"Result: {r['key']} | score={r['score']:.4f} - {r['summary']}")

    return {"results": formatted}




# ------------------------------------------------------------------
# ---------------------- Methods for testing -----------------------

# --- search_vector_db_for_similar_jira_tickets ---
# print(search_vector_db_for_similar_jira_tickets('Develop new botton')) # test
