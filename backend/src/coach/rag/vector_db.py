import chromadb
from chromadb.utils import embedding_functions

def get_collection(persist_dir: str):
    """Initializes and returns a persistent ChromaDB collection."""
    client = chromadb.PersistentClient(path=persist_dir)
    embedding_func = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name="chess_rag",
        embedding_function=embedding_func
    )

def reset_collection(persist_dir: str):
    """Deletes and recreates the ChromaDB collection to clear previous documents."""
    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(name="chess_rag")
    except Exception:
        pass
    embedding_func = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name="chess_rag",
        embedding_function=embedding_func
    )
