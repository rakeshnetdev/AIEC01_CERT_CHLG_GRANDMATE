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
