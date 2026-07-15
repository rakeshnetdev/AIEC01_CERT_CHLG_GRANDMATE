import json
import logging
import httpx
from typing import List, Optional
from coach.schemas.models import Game
from coach.ingestion.pgn import parse_pgn
from coach.utils.cache import get_cached_http_response, cache_http_response

logger = logging.getLogger(__name__)

def fetch_lichess_games(username: str, max_games: int = 10, token: Optional[str] = None) -> List[Game]:
    """Fetches games for a Lichess user, reconstructs PGN from NDJSON, and caches responses."""
    cache_key = f"lichess_{username.lower()}_{max_games}"
    
    cached_text = get_cached_http_response(cache_key)
    if cached_text:
        logger.info(f"Retrieved Lichess games for {username} from cache.")
        return _parse_lichess_ndjson(cached_text, username)
        
    url = f"https://lichess.org/api/games/user/{username}"
    params = {
        "max": max_games,
        "opening": "true",
        "moves": "true"
    }
    headers = {
        "Accept": "application/x-ndjson"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    logger.info(f"Fetching Lichess games for {username} from API...")
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=15.0)
        if response.status_code == 200:
            text_content = response.text
            cache_http_response(cache_key, text_content)
            return _parse_lichess_ndjson(text_content, username)
        else:
            logger.error(f"Lichess API returned status code {response.status_code}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Failed to fetch Lichess games: {e}")
        return []


def _parse_lichess_ndjson(ndjson_text: str, username: str) -> List[Game]:
    """Helper to parse Lichess NDJSON string and return Game objects."""
    games = []
    for line in ndjson_text.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            
            # Players handling
            players = data.get("players", {})
            white_data = players.get("white", {})
            black_data = players.get("black", {})
            
            white_name = white_data.get("user", {}).get("name") or white_data.get("name") or "AI"
            black_name = black_data.get("user", {}).get("name") or black_data.get("name") or "AI"
            
            # Result mapping
            winner = data.get("winner")
            if winner == "white":
                result = "1-0"
            elif winner == "black":
                result = "0-1"
            else:
                result = "1/2-1/2"
                
            # Construct a virtual PGN string
            pgn_lines = [
                f'[Event "{data.get("speed", "Casual").title()} Game"]',
                f'[Site "https://lichess.org/{data.get("id")}"]',
                f'[White "{white_name}"]',
                f'[Black "{black_name}"]',
                f'[Result "{result}"]'
            ]
            
            if "opening" in data:
                pgn_lines.append(f'[Opening "{data["opening"].get("name")}"]')
                
            white_rating = white_data.get("rating")
            if white_rating:
                pgn_lines.append(f'[WhiteElo "{white_rating}"]')
                
            black_rating = black_data.get("rating")
            if black_rating:
                pgn_lines.append(f'[BlackElo "{black_rating}"]')
                
            clock = data.get("clock")
            if clock:
                initial = clock.get("initial")
                inc = clock.get("increment")
                pgn_lines.append(f'[TimeControl "{initial}+{inc}"]')
                
            pgn_lines.append("")
            pgn_lines.append(data.get("moves", ""))
            
            pgn_str = "\n".join(pgn_lines)
            
            # Re-use our robust PGN parser
            game = parse_pgn(pgn_str, "lichess", username)
            games.append(game)
        except Exception as e:
            logger.warning(f"Failed parsing Lichess NDJSON line: {e}")
            continue
            
    return games
