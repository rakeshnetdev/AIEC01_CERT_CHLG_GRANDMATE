import os
import logging
from pathlib import Path
from typing import List, Dict
from coach.rag.loader import load_openings, load_markdown_notes
from coach.rag.vector_db import get_collection, reset_collection

logger = logging.getLogger(__name__)

def ingest_corpus(corpus_dir: str, persist_dir: str) -> None:
    """Ingests all corpus files (TSV openings + MD concept notes) into local ChromaDB."""
    logger.info(f"Ingesting corpus from {corpus_dir} to vector store at {persist_dir}")
    
    corpus_path = Path(corpus_dir)
    openings_file = corpus_path / "openings.tsv"
    
    # 1. Load openings
    chunks = load_openings(openings_file)
    
    # 2. Load markdown files
    for md_file in corpus_path.glob("*.md"):
        chunks.extend(load_markdown_notes(md_file))
        
    if not chunks:
        logger.warning("No corpus chunks found to ingest.")
        return
        
    # Reset collection to clear past data
    collection = reset_collection(persist_dir)
    
    ids = []
    documents = []
    metadatas = []
    
    for idx, chunk in enumerate(chunks):
        chunk_type = chunk["metadata"].get("type", "chunk")
        ids.append(f"{chunk_type}_{idx}")
        documents.append(chunk["text"])
        metadatas.append(chunk["metadata"])
        
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    logger.info(f"Ingested {len(chunks)} chunks into ChromaDB.")


def retrieve_context(query: str, persist_dir: str, limit: int = 2) -> List[Dict]:
    """Retrieves top semantically matching chunks from ChromaDB for a given query."""
    logger.info(f"Querying vector store at {persist_dir} with: '{query}'")
    
    collection = get_collection(persist_dir)
    query_results = collection.query(
        query_texts=[query],
        n_results=limit
    )
    
    results = []
    if query_results and "documents" in query_results and query_results["documents"]:
        documents = query_results["documents"][0]
        metadatas = query_results["metadatas"][0] if "metadatas" in query_results and query_results["metadatas"] else []
        ids = query_results["ids"][0] if "ids" in query_results and query_results["ids"] else []
        
        for idx in range(len(documents)):
            results.append({
                "id": ids[idx],
                "text": documents[idx],
                "metadata": metadatas[idx] if idx < len(metadatas) else {}
            })
            
    return results
