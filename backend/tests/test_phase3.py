import os
import shutil
import pytest
from pathlib import Path
from coach.rag.loader import load_openings, load_markdown_notes
from coach.rag.pipeline import ingest_corpus, retrieve_context

def test_loaders():
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    
    # 1. Test Openings Loader
    openings_file = corpus_dir / "openings.tsv"
    openings_chunks = load_openings(openings_file)
    
    assert len(openings_chunks) >= 3
    assert openings_chunks[0]["metadata"]["type"] == "opening"
    names = [c["metadata"]["name"] for c in openings_chunks]
    assert "Sicilian Defense" in names
    
    # 2. Test Markdown Concept Notes Loader
    notes_file = corpus_dir / "concept_notes_tactics.md"
    concept_chunks = load_markdown_notes(notes_file)
    
    assert len(concept_chunks) >= 2
    
    pin_chunk = next(c for c in concept_chunks if c["metadata"]["title"] == "The Pin")
    assert pin_chunk["metadata"]["type"] == "concept"
    assert "absolute pins" in pin_chunk["text"].lower()
    
    fork_chunk = next(c for c in concept_chunks if c["metadata"]["title"] == "The Fork")
    assert fork_chunk["metadata"]["type"] == "concept"
    assert "L-shaped" in fork_chunk["text"]


def test_ingest_and_retrieve(tmp_path):
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    persist_dir = tmp_path / "chroma_test"
    
    # Ingest the MVP corpus
    ingest_corpus(str(corpus_dir), str(persist_dir))
    
    # 1. Semantic search for "Sicilian"
    results = retrieve_context("Sicilian Defense", str(persist_dir), limit=3)
    assert len(results) > 0
    names = [r["metadata"].get("name") for r in results if r["metadata"]["type"] == "opening"]
    assert any("Sicilian" in name for name in names if name)
    
    # 2. Semantic search for "pinned piece"
    results = retrieve_context("pinned piece", str(persist_dir), limit=10)
    concept_results = [r for r in results if r["metadata"]["type"] == "concept"]
    assert len(concept_results) > 0
    assert concept_results[0]["metadata"]["title"] == "The Pin"
    
    # 3. Semantic search for "double attack knight"
    results = retrieve_context("double attack knight fork", str(persist_dir), limit=10)
    concept_results = [r for r in results if r["metadata"]["type"] == "concept"]
    assert len(concept_results) > 0
    assert concept_results[0]["metadata"]["title"] == "The Fork"
