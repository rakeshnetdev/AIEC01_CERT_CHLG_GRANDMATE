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


def get_collection(persist_dir: str):
    """Initializes and returns a persistent ChromaDB collection.
    
    Handles embedding function conflicts by loading the collection without 
    specifying the function if a mismatch is detected.
    """
    import chromadb

    client = chromadb.PersistentClient(path=persist_dir)
    embedding_func = _get_embedding_function()
    try:
        return client.get_or_create_collection(
            name="chess_rag",
            embedding_function=embedding_func
        )
    except ValueError as e:
        if "embedding function" in str(e).lower():
            logger.warning("Embedding function mismatch detected. Loading collection using persisted configuration.")
            return client.get_collection(name="chess_rag")
        raise e


def reset_collection(persist_dir: str):
    """Deletes and recreates the ChromaDB collection to clear previous documents."""
    import chromadb

    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(name="chess_rag")
    except Exception:
        pass
    embedding_func = _get_embedding_function()
    return client.get_or_create_collection(
        name="chess_rag",
        embedding_function=embedding_func
    )
