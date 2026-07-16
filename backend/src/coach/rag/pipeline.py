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
    
    # Invalidate cached BM25 index after fresh ingestion
    global _BM25_CACHE
    _BM25_CACHE = None


# Global cache for BM25 instance and lookups: (bm25_instance, doc_ids, doc_lookup)
_BM25_CACHE = None

def get_bm25_index(collection) -> tuple | None:
    """Helper to lazily construct and cache the BM25 lexical index from ChromaDB."""
    global _BM25_CACHE
    if _BM25_CACHE is not None:
        return _BM25_CACHE
        
    logger.info("Initializing and caching BM25 index from ChromaDB documents...")
    all_docs = collection.get()
    if not all_docs or not all_docs.get("documents"):
        return None
        
    doc_ids = all_docs["ids"]
    documents = all_docs["documents"]
    metadatas = all_docs["metadatas"] or [{} for _ in range(len(doc_ids))]
    
    doc_lookup = {
        doc_ids[i]: {
            "id": doc_ids[i],
            "text": documents[i],
            "metadata": metadatas[i] if metadatas[i] else {}
        }
        for i in range(len(doc_ids))
    }
    
    import re
    from rank_bm25 import BM25Okapi
    
    def tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())
        
    tokenized_corpus = [tokenize(doc) for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    
    _BM25_CACHE = (bm25, doc_ids, doc_lookup)
    return _BM25_CACHE


def retrieve_context(query: str, persist_dir: str, limit: int = 2) -> List[Dict]:
    """Retrieves top semantically + lexically matching chunks from ChromaDB and BM25 using RRF."""
    logger.info(f"Querying vector store (hybrid) at {persist_dir} with: '{query}'")
    
    collection = get_collection(persist_dir)
    
    # 1. Fetch or load the cached BM25 index to avoid pulling all documents on every query
    bm25_data = get_bm25_index(collection)
    if not bm25_data:
        logger.warning("No documents found in ChromaDB to build BM25 index.")
        return []
        
    bm25, doc_ids, doc_lookup = bm25_data
    
    # 2. Dense Vector Search (ChromaDB)
    # We query ChromaDB for top 10 candidates (or len(doc_ids) if smaller)
    vector_k = min(10, len(doc_ids))
    dense_results = []
    try:
        query_results = collection.query(
            query_texts=[query],
            n_results=vector_k
        )
        if query_results and "documents" in query_results and query_results["documents"]:
            q_docs = query_results["documents"][0]
            q_ids = query_results["ids"][0] if "ids" in query_results else []
            for i in range(len(q_docs)):
                dense_results.append(q_ids[i])
    except Exception as e:
        logger.error(f"Error querying ChromaDB vector search: {e}")
        
    # 3. Sparse Lexical Search (BM25)
    import re
    def tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())
        
    tokenized_query = tokenize(query)
    bm25_scores = bm25.get_scores(tokenized_query)
    
    # Sort docs by BM25 score desc
    bm25_k = min(10, len(doc_ids))
    sorted_indices = sorted(range(len(bm25_scores)), key=lambda idx: bm25_scores[idx], reverse=True)
    
    sparse_results = []
    for idx in sorted_indices[:bm25_k]:
        # Only include if score > 0 to avoid matching empty terms
        if bm25_scores[idx] > 0.0:
            sparse_results.append(doc_ids[idx])
            
    # 4. Reciprocal Rank Fusion (RRF)
    rrf_scores = {}
    rrf_constant = 60
    
    # Dense list scoring
    for rank, doc_id in enumerate(dense_results, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rrf_constant + rank)
        
    # Sparse list scoring
    for rank, doc_id in enumerate(sparse_results, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rrf_constant + rank)
        
    # Sort by RRF score descending
    sorted_rrf = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    
    # If RRF results are empty, fall back to top vector results
    if not sorted_rrf:
        logger.warning("RRF fusion returned empty. Falling back to dense vector results.")
        sorted_rrf = [(doc_id, 1.0) for doc_id in dense_results]
        
    # Take top `limit` results
    final_results = []
    for doc_id, rrf_score in sorted_rrf[:limit]:
        if doc_id in doc_lookup:
            item = doc_lookup[doc_id].copy()
            item["rrf_score"] = rrf_score
            final_results.append(item)
            
    logger.info(f"Hybrid RRF retrieval returned {len(final_results)} items.")
    return final_results
