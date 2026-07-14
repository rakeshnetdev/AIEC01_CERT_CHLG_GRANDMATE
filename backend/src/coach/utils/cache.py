import sqlite3
import json
import logging
from typing import Optional, List, Dict, Any
from config.settings import get_settings

logger = logging.getLogger(__name__)

def get_cache_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Returns a sqlite3 connection to the database and ensures cache tables are initialized."""
    if not db_path:
        db_path = get_settings().db_path
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Initialize tables
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS http_cache (
                url TEXT PRIMARY KEY,
                response_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS engine_cache (
                fen TEXT,
                depth INTEGER,
                best_uci TEXT,
                pv_uci TEXT, -- JSON list of moves
                score_cp INTEGER,
                PRIMARY KEY (fen, depth)
            )
        """)
    
    return conn


def get_cached_http_response(url: str, db_path: Optional[str] = None) -> Optional[str]:
    """Retrieve cached HTTP response if it exists."""
    try:
        conn = get_cache_db(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT response_text FROM http_cache WHERE url = ?", (url,))
        row = cursor.fetchone()
        conn.close()
        if row:
            logger.debug(f"HTTP Cache HIT: {url}")
            return row["response_text"]
    except Exception as e:
        logger.error(f"Error reading HTTP cache: {e}")
    return None


def cache_http_response(url: str, response_text: str, db_path: Optional[str] = None) -> None:
    """Save HTTP response to the cache."""
    try:
        conn = get_cache_db(db_path)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO http_cache (url, response_text) VALUES (?, ?)",
                (url, response_text)
            )
        conn.close()
        logger.debug(f"HTTP Cache WRITE: {url}")
    except Exception as e:
        logger.error(f"Error writing to HTTP cache: {e}")


def get_cached_engine_eval(fen: str, depth: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve cached engine evaluation for a given FEN and depth."""
    try:
        conn = get_cache_db(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT best_uci, pv_uci, score_cp FROM engine_cache WHERE fen = ? AND depth = ?",
            (fen, depth)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            logger.debug(f"Engine Cache HIT: {fen} @ depth {depth}")
            return {
                "best_uci": row["best_uci"],
                "pv_uci": json.loads(row["pv_uci"]),
                "score_cp": row["score_cp"]
            }
    except Exception as e:
        logger.error(f"Error reading engine cache: {e}")
    return None


def cache_engine_eval(
    fen: str, 
    depth: int, 
    best_uci: str, 
    pv_uci: List[str], 
    score_cp: int, 
    db_path: Optional[str] = None
) -> None:
    """Save engine evaluation to the cache."""
    try:
        conn = get_cache_db(db_path)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO engine_cache (fen, depth, best_uci, pv_uci, score_cp) VALUES (?, ?, ?, ?, ?)",
                (fen, depth, best_uci, json.dumps(pv_uci), score_cp)
            )
        conn.close()
        logger.debug(f"Engine Cache WRITE: {fen} @ depth {depth}")
    except Exception as e:
        logger.error(f"Error writing to engine cache: {e}")
