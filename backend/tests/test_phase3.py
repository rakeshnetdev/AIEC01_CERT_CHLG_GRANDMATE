import os
import shutil
import pytest
from pathlib import Path
from coach.rag.loader import load_openings, load_markdown_notes
from coach.rag.pipeline import ingest_corpus, retrieve_context

def test_loaders():
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    
    # 1. Test Openings Loader
    openings_file = corpus_dir / "strategies" / "openings.tsv"
    openings_chunks = load_openings(openings_file)
    
    assert len(openings_chunks) >= 3
    assert openings_chunks[0]["metadata"]["type"] == "opening"
    names = [c["metadata"]["name"] for c in openings_chunks]
    assert "Sicilian Defense" in names
    
    # 2. Test Markdown Concept Notes Loader
    notes_file = corpus_dir / "rules" / "concept_notes_tactics.md"
    concept_chunks = load_markdown_notes(notes_file)
    
    assert len(concept_chunks) >= 2
    
    pin_chunk = next(c for c in concept_chunks if c["metadata"]["title"] == "The Pin")
    assert pin_chunk["metadata"]["type"] == "concept"
    assert "absolute pins" in pin_chunk["text"].lower()
    
    fork_chunk = next(c for c in concept_chunks if c["metadata"]["title"] == "The Fork")
    assert fork_chunk["metadata"]["type"] == "concept"
    assert "L-shaped" in fork_chunk["text"]
    
    # 3. Test PDF Loader
    pdf_file = corpus_dir / "rules" / "FIDE - LawsOfChess.pdf"
    from coach.rag.loader import load_pdf
    pdf_chunks = load_pdf(pdf_file)
    assert len(pdf_chunks) > 0
    assert pdf_chunks[0]["metadata"]["source"] == "FIDE - LawsOfChess.pdf"
    assert pdf_chunks[0]["metadata"]["type"] == "pdf_chunk"


def test_ingest_and_retrieve(tmp_path):
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    persist_dir = tmp_path / "chroma_test"
    
    # Ingest the MVP corpus
    ingest_corpus(str(corpus_dir), str(persist_dir))
    
    # 1. Semantic search for "Sicilian"
    results = retrieve_context("Sicilian Defense", str(persist_dir), limit=3)
    assert len(results) > 0
    names = [r["metadata"].get("name") for r in results if r["metadata"].get("type") == "opening"]
    assert any("Sicilian" in name for name in names if name)
    
    # 2. Semantic search for "pinned piece"
    results = retrieve_context("pinned piece", str(persist_dir), limit=10)
    concept_results = [r for r in results if r["metadata"].get("type") == "concept"]
    assert len(concept_results) > 0
    assert concept_results[0]["metadata"]["title"] == "The Pin"
    
    # 3. Test bucket filtering
    # "Sicilian Defense" should be in strategies, not rules
    strategy_results = retrieve_context("Sicilian Defense", str(persist_dir), limit=3, bucket="strategies")
    assert len(strategy_results) > 0
    strategy_names = [r["metadata"].get("name") for r in strategy_results if r["metadata"].get("type") == "opening"]
    assert any("Sicilian" in name for name in strategy_names if name)
    
    rules_results = retrieve_context("Sicilian Defense", str(persist_dir), limit=3, bucket="rules")
    rules_names = [r["metadata"].get("name") for r in rules_results if r["metadata"].get("type") == "opening"]
    assert not any("Sicilian" in name for name in rules_names if name)
    
    # Rules search should pull FIDE Laws of Chess
    fide_results = retrieve_context("castling rules", str(persist_dir), limit=5, bucket="rules")
    assert len(fide_results) > 0
    sources = [r["metadata"].get("source") for r in fide_results]
    assert "FIDE - LawsOfChess.pdf" in sources or "concept_notes_tactics.md" in sources

