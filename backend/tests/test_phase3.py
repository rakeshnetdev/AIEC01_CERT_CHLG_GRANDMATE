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
    
    assert len(openings_chunks) == 3
    assert openings_chunks[0]["metadata"]["type"] == "opening"
    assert openings_chunks[0]["metadata"]["name"] == "Sicilian Defense"
    assert "Sicilian Defense" in openings_chunks[0]["text"]
    assert "1. e4 c5" in openings_chunks[0]["text"]
    
    # 2. Test Markdown Concept Notes Loader
    notes_file = corpus_dir / "concept_notes_tactics.md"
    concept_chunks = load_markdown_notes(notes_file)
    
    assert len(concept_chunks) == 2
    assert concept_chunks[0]["metadata"]["type"] == "concept"
    assert concept_chunks[0]["metadata"]["title"] == "The Pin"
    assert "The Pin" in concept_chunks[0]["text"]
    assert "absolute pins" in concept_chunks[0]["text"].lower()
    
    assert concept_chunks[1]["metadata"]["type"] == "concept"
    assert concept_chunks[1]["metadata"]["title"] == "The Fork"
    assert "L-shaped movement" in concept_chunks[1]["text"]


def test_ingest_and_retrieve(tmp_path):
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    persist_dir = tmp_path / "chroma_test"
    
    # Ingest the MVP corpus
    ingest_corpus(str(corpus_dir), str(persist_dir))
    
    # 1. Semantic search for "Sicilian"
    results = retrieve_context("Sicilian Defense", str(persist_dir), limit=1)
    assert len(results) > 0
    assert results[0]["metadata"]["type"] == "opening"
    assert "Sicilian" in results[0]["metadata"]["name"]
    
    # 2. Semantic search for "pinned piece"
    results = retrieve_context("pinned piece", str(persist_dir), limit=1)
    assert len(results) > 0
    assert results[0]["metadata"]["type"] == "concept"
    assert results[0]["metadata"]["title"] == "The Pin"
    
    # 3. Semantic search for "double attack knight"
    results = retrieve_context("double attack knight", str(persist_dir), limit=1)
    assert len(results) > 0
    assert results[0]["metadata"]["type"] == "concept"
    assert results[0]["metadata"]["title"] == "The Fork"
