import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
from coach.rag.loader import load_openings, load_markdown_notes, load_pdf
from coach.rag.vector_db import get_collection, reset_collection

logger = logging.getLogger(__name__)

def ingest_corpus(corpus_dir: str, persist_dir: str) -> None:
    """Ingests all corpus files (PDF, TSV, MD) from bucket directories into local ChromaDB.
    
    This function discovers the partitioned directories ('rules' and 'strategies'),
    loads files using appropriate loaders (TSV row-by-row, markdown by headers,
    PDF page-by-page), and assigns the corresponding metadata 'bucket' tag.
    """
    logger.info(f"Ingesting corpus from {corpus_dir} to vector store at {persist_dir}")
    
    corpus_path = Path(corpus_dir)
    chunks = []
    
    # Nested helper to inspect a directory and load all supported formats
    def load_folder(folder_path: Path, bucket_name: str):
        folder_chunks = []
        # Load TSV (e.g. openings.tsv)
        for tsv_file in folder_path.glob("*.tsv"):
            for chunk in load_openings(tsv_file):
                chunk["metadata"]["bucket"] = bucket_name
                folder_chunks.append(chunk)
        # Load markdown notes (e.g. tactics.md)
        for md_file in folder_path.glob("*.md"):
            for chunk in load_markdown_notes(md_file):
                chunk["metadata"]["bucket"] = bucket_name
                folder_chunks.append(chunk)
        # Load PDF rulebooks (e.g. FIDE - LawsOfChess.pdf)
        for pdf_file in folder_path.glob("*.pdf"):
            for chunk in load_pdf(pdf_file):
                chunk["metadata"]["bucket"] = bucket_name
                folder_chunks.append(chunk)
        return folder_chunks

    # Look for partitioned bucket folders: 'rules' and 'strategies'
    has_buckets = False
    for bucket in ["rules", "strategies"]:
        bucket_dir = corpus_path / bucket
        if bucket_dir.exists() and bucket_dir.is_dir():
            has_buckets = True
            logger.info(f"Loading bucket '{bucket}' from {bucket_dir}")
            chunks.extend(load_folder(bucket_dir, bucket))

    # Fallback to root directory if no bucket folders exist (legacy support)
    if not has_buckets:
        logger.info("No bucket subdirectories found. Ingesting files at root as 'strategies'")
        for chunk in load_folder(corpus_path, "strategies"):
            chunks.append(chunk)
        
    if not chunks:
        logger.warning("No corpus chunks found to ingest.")
        return
        
    # Reset collection to clear past data
    collection = reset_collection(persist_dir)
    
    ids = []
    documents = []
    metadatas = []
    
    # Prepare payloads for batch injection into ChromaDB
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


def _retrieve_dense_only(query: str, collection, limit: int, doc_ids: List[str], doc_lookup: dict, bucket: Optional[str] = None) -> List[Dict]:
    """Queries only the dense vector index and formats the top results, optionally filtering by bucket."""
    vector_k = min(10, len(doc_ids))
    dense_results = []
    try:
        query_results = collection.query(
            query_texts=[query],
            where={"bucket": bucket} if bucket else None,
            n_results=vector_k
        )
        if query_results and "documents" in query_results and query_results["documents"]:
            q_docs = query_results["documents"][0]
            q_ids = query_results["ids"][0] if "ids" in query_results else []
            for i in range(len(q_docs)):
                dense_results.append(q_ids[i])
    except Exception as e:
        logger.error(f"Error querying ChromaDB vector search: {e}")
        
    final_results = []
    for doc_id in dense_results[:limit]:
        if doc_id in doc_lookup:
            item = doc_lookup[doc_id].copy()
            item["rrf_score"] = 1.0
            final_results.append(item)
    return final_results


def _retrieve_sparse_only(query: str, bm25, limit: int, doc_ids: List[str], doc_lookup: dict, bucket: Optional[str] = None) -> List[Dict]:
    """Queries only the cached BM25 sparse lexical index and formats the top results, optionally filtering by bucket."""
    import re
    def tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())
        
    tokenized_query = tokenize(query)
    
    if bucket:
        # Filter doc_ids for this bucket and build a temporary BM25 index
        filtered_ids = []
        filtered_texts = []
        for doc_id in doc_ids:
            if doc_lookup[doc_id]["metadata"].get("bucket") == bucket:
                filtered_ids.append(doc_id)
                filtered_texts.append(doc_lookup[doc_id]["text"])
                
        if not filtered_ids:
            return []
            
        from rank_bm25 import BM25Okapi
        tokenized_corpus = [tokenize(doc) for doc in filtered_texts]
        temp_bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = temp_bm25.get_scores(tokenized_query)
        
        bm25_k = min(10, len(filtered_ids))
        sorted_indices = sorted(range(len(bm25_scores)), key=lambda idx: bm25_scores[idx], reverse=True)
        
        sparse_results = []
        for idx in sorted_indices[:bm25_k]:
            if bm25_scores[idx] > 0.0:
                sparse_results.append(filtered_ids[idx])
    else:
        # Global BM25 scoring
        bm25_scores = bm25.get_scores(tokenized_query)
        bm25_k = min(10, len(doc_ids))
        sorted_indices = sorted(range(len(bm25_scores)), key=lambda idx: bm25_scores[idx], reverse=True)
        
        sparse_results = []
        for idx in sorted_indices[:bm25_k]:
            if bm25_scores[idx] > 0.0:
                sparse_results.append(doc_ids[idx])
            
    final_results = []
    for doc_id in sparse_results[:limit]:
        if doc_id in doc_lookup:
            item = doc_lookup[doc_id].copy()
            item["rrf_score"] = 1.0
            final_results.append(item)
    return final_results


def _retrieve_hybrid_fused(query: str, collection, bm25, limit: int, doc_ids: List[str], doc_lookup: dict, bucket: Optional[str] = None) -> List[Dict]:
    """Queries both dense and sparse indexes in parallel and aggregates rankings via RRF, optionally filtering by bucket."""
    dense_items = _retrieve_dense_only(query, collection, len(doc_ids), doc_ids, doc_lookup, bucket)
    dense_results = [item["id"] for item in dense_items]
        
    sparse_items = _retrieve_sparse_only(query, bm25, len(doc_ids), doc_ids, doc_lookup, bucket)
    sparse_results = [item["id"] for item in sparse_items]
            
    rrf_scores = {}
    rrf_constant = 60
    
    for rank, doc_id in enumerate(dense_results, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rrf_constant + rank)
        
    for rank, doc_id in enumerate(sparse_results, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rrf_constant + rank)
        
    sorted_rrf = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    
    if not sorted_rrf:
        logger.warning("RRF fusion returned empty. Falling back to dense vector results.")
        sorted_rrf = [(doc_id, 1.0) for doc_id in dense_results]
        
    final_results = []
    for doc_id, rrf_score in sorted_rrf[:limit]:
        if doc_id in doc_lookup:
            item = doc_lookup[doc_id].copy()
            item["rrf_score"] = rrf_score
            final_results.append(item)
    return final_results


def retrieve_context(query: str, persist_dir: str, limit: int = 2, retriever_type: Optional[str] = None, bucket: Optional[str] = None) -> List[Dict]:
    """Retrieves top matching chunks from ChromaDB and/or BM25 based on the retriever_type, with optional bucket filtering."""
    if not retriever_type:
        from config.settings import get_settings
        retriever_type = get_settings().retriever_type

    logger.info(f"Querying vector store ({retriever_type}) at {persist_dir} (bucket: {bucket}) with: '{query}'")
    
    collection = get_collection(persist_dir)
    
    bm25_data = get_bm25_index(collection)
    if not bm25_data:
        logger.warning("No documents found in ChromaDB to build BM25 index.")
        return []
        
    bm25, doc_ids, doc_lookup = bm25_data
    
    if retriever_type == "dense":
        return _retrieve_dense_only(query, collection, limit, doc_ids, doc_lookup, bucket)
    elif retriever_type == "sparse":
        return _retrieve_sparse_only(query, bm25, limit, doc_ids, doc_lookup, bucket)
    else:
        return _retrieve_hybrid_fused(query, collection, bm25, limit, doc_ids, doc_lookup, bucket)
