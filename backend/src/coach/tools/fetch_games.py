import logging
from typing import List, Dict, Any
from coach.ingestion.lichess import fetch_lichess_games
from coach.ingestion.chesscom import fetch_chesscom_games

logger = logging.getLogger(__name__)

def fetch_games(username: str, source: str, max_games: int = 10) -> List[Dict[str, Any]]:
    """Agent tool that fetches games for a user from a given source (lichess or chesscom).
    
    Returns a list of Game dictionaries.
    """
    logger.info(f"fetch_games tool called for {username} via {source} (max {max_games})")
    
    source_lower = source.lower()
    games = []
    
    if source_lower == "lichess":
        games = fetch_lichess_games(username, max_games=max_games)
    elif source_lower == "chesscom" or source_lower == "chess.com":
        games = fetch_chesscom_games(username, max_games=max_games)
    else:
        logger.error(f"Unsupported source format in fetch_games: {source}")
        return []
        
    return [game.model_dump() for game in games]
