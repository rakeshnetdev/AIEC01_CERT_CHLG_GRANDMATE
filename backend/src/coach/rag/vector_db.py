import os
import logging
from config.settings import get_settings

# NOTE: chromadb is imported lazily inside the functions below. At module scope it added
# ~0.9s to every import of coach.rag.pipeline, which sits on coach.agent.graph's import
# path and so slowed `langgraph dev` startup. Nothing here touches chromadb at import time.

logger = logging.getLogger(__name__)

def _get_embedding_function():
    """Initializes and returns the OpenAI embedding function using configured settings.
    
    Falls back to Chroma's local DefaultEmbeddingFunction if the OpenAI API Key is not present.
    """
    from chromadb.utils import embedding_functions

    settings = get_settings()
    api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
    
    if api_key and api_key != "mock_key":
        logger.info(f"Using OpenAIEmbeddingFunction with model '{settings.embed_model}'")
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=settings.embed_model or "text-embedding-3-small"
        )
    else:
        logger.warning("OpenAI API key not configured. Falling back to local DefaultEmbeddingFunction.")
        return embedding_functions.DefaultEmbeddingFunction()


# The persistent client and its collection handle are process-stable: the DB path and the
# embedding function never change within a run. Rebuilding them on every retrieval re-opened the
# client and re-instantiated the OpenAI embedding function each time, so they are memoized per
# persist_dir here. reset_collection() must invalidate this cache after a re-ingest.
_COLLECTION_CACHE: dict = {}


def get_collection(persist_dir: str):
    """Initializes and returns a persistent ChromaDB collection (memoized per persist_dir).

    Handles embedding function conflicts by loading the collection without
    specifying the function if a mismatch is detected.
    """
    cached = _COLLECTION_CACHE.get(persist_dir)
    if cached is not None:
        return cached

    import chromadb

    client = chromadb.PersistentClient(path=persist_dir)
    embedding_func = _get_embedding_function()
    try:
        collection = client.get_or_create_collection(
            name="chess_rag",
            embedding_function=embedding_func
        )
    except ValueError as e:
        if "embedding function" in str(e).lower():
            logger.warning("Embedding function mismatch detected. Loading collection using persisted configuration.")
            collection = client.get_collection(name="chess_rag")
        else:
            raise e

    _COLLECTION_CACHE[persist_dir] = collection
    return collection


def reset_collection(persist_dir: str):
    """Deletes and recreates the ChromaDB collection to clear previous documents."""
    import chromadb

    # The old collection handle is now stale; drop it so get_collection rebuilds on next use.
    _COLLECTION_CACHE.pop(persist_dir, None)

    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(name="chess_rag")
    except Exception:
        pass
    embedding_func = _get_embedding_function()
    collection = client.get_or_create_collection(
        name="chess_rag",
        embedding_function=embedding_func
    )
    _COLLECTION_CACHE[persist_dir] = collection
    return collection
