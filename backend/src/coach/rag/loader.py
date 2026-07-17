import csv
from pathlib import Path
from typing import List, Dict

def load_openings(file_path: Path) -> List[Dict]:
    """Loads chess openings from a TSV file, converting each row into a chunk."""
    chunks = []
    if not file_path.exists():
        return chunks
        
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            name = row.get("name", "").strip()
            pgn = row.get("pgn", "").strip()
            description = row.get("description", "").strip()
            moves = row.get("moves", "").strip()
            
            if not name:
                continue
                
            text = f"Opening: {name}. PGN: {pgn}. Description: {description}. Moves: {moves}."
            metadata = {
                "type": "opening",
                "name": name,
                "pgn": pgn
            }
            chunks.append({"text": text, "metadata": metadata})
            
    return chunks


def load_markdown_notes(file_path: Path) -> List[Dict]:
    """Parses chess concept markdown files, chunking by H2 (##) headings."""
    chunks = []
    if not file_path.exists():
        return chunks
        
    current_title = None
    current_lines = []
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                # Save previous chunk
                if current_title:
                    text_content = "".join(current_lines).strip()
                    chunks.append({
                        "text": f"## {current_title}\n{text_content}",
                        "metadata": {
                            "type": "concept",
                            "title": current_title
                        }
                    })
                current_title = line[3:].strip()
                current_lines = []
            elif current_title:
                current_lines.append(line)
                
        # Append final chunk
        if current_title:
            text_content = "".join(current_lines).strip()
            chunks.append({
                "text": f"## {current_title}\n{text_content}",
                "metadata": {
                    "type": "concept",
                    "title": current_title
                }
            })
            
    return chunks


def load_pdf(file_path: Path) -> List[Dict]:
    """Loads text from a PDF file page-by-page, chunking each page recursively.
    
    This function parses official documents (like the FIDE Laws of Chess PDF)
    and chunks them into small overlapping segments for context-grounded retrieval.
    
    Args:
        file_path (Path): Path to the target PDF file.
        
    Returns:
        List[Dict]: List of chunks with 'text' and 'metadata' structures.
    """
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    chunks = []
    if not file_path.exists():
        return chunks
        
    try:
        # Load the PDF file page-by-page using LangChain's community loader
        loader = PyPDFLoader(str(file_path))
        pages = loader.load()
        
        # Split pages recursively into smaller segments to fit within LLM context windows.
        # chunk_size=1000 characters and chunk_overlap=200 characters is chosen to ensure
        # that rule articles or definitions are not truncated abruptly at boundary points.
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        split_docs = text_splitter.split_documents(pages)
        
        for idx, doc in enumerate(split_docs):
            chunks.append({
                "text": doc.page_content,
                "metadata": {
                    "source": file_path.name,
                    "type": "pdf_chunk",
                    "chunk_id": idx
                }
            })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error loading PDF {file_path}: {e}")
        
    return chunks

