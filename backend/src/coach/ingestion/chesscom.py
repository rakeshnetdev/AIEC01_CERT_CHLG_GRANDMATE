import datetime
import json
import time
import logging
import httpx
from typing import List, Optional
from coach.schemas.models import Game
from coach.ingestion.pgn import parse_pgn
from coach.utils.cache import get_cached_http_response, cache_http_response

logger = logging.getLogger(__name__)

def fetch_chesscom_games(username: str, months: int = 1, max_games: int = 10) -> List[Game]:
    """Fetches games for a Chess.com player going back N months, with backoff for 429s."""
    games: List[Game] = []
    
    # Generate list of (year, month) to fetch
    target_months = []
    now = datetime.datetime.now()
    curr_year = now.year
    curr_month = now.month
    
    for _ in range(months):
        target_months.append((curr_year, curr_month))
        curr_month -= 1
        if curr_month == 0:
            curr_month = 12
            curr_year -= 1
            
    headers = {
        "User-Agent": "Grandmate Chess Coach (contact: sriraki@netdev.com)"
    }
    
    for year, month in target_months:
        if len(games) >= max_games:
            break
            
        cache_key = f"chesscom_{username.lower()}_{year}_{month:02d}"
        cached_text = get_cached_http_response(cache_key)
        
        month_data = None
        if cached_text:
            logger.info(f"Retrieved Chess.com games for {username} ({year}-{month:02d}) from cache.")
            try:
                month_data = json.loads(cached_text)
            except json.JSONDecodeError:
                pass
                
        if not month_data:
            url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month:02d}"
            logger.info(f"Fetching Chess.com games from {url}...")
            
            # Request with 429 rate limit backoff
            response_text = None
            for attempt in range(3):
                try:
                    response = httpx.get(url, headers=headers, timeout=15.0)
                    if response.status_code == 200:
                        response_text = response.text
                        break
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 2))
                        logger.warning(f"Rate limited (429) by Chess.com. Sleeping {retry_after}s before retry.")
                        time.sleep(retry_after)
                    elif response.status_code == 404:
                        logger.warning(f"No games found for Chess.com player {username} in {year}-{month:02d}.")
                        break
                    else:
                        logger.error(f"Chess.com returned status {response.status_code}: {response.text}")
                        break
                except Exception as e:
                    logger.error(f"Error fetching from Chess.com: {e}")
                    time.sleep(1)
                    
            if response_text:
                cache_http_response(cache_key, response_text)
                try:
                    month_data = json.loads(response_text)
                except json.JSONDecodeError:
                    pass
                    
        if month_data and "games" in month_data:
            # Parse games in reverse order (most recent first)
            for g_dict in reversed(month_data["games"]):
                if len(games) >= max_games:
                    break
                pgn_str = g_dict.get("pgn")
                if pgn_str:
                    try:
                        game = parse_pgn(pgn_str, "chesscom", username)
                        games.append(game)
                    except Exception as e:
                        logger.warning(f"Failed parsing Chess.com game PGN: {e}")
                        continue
                        
    return games[:max_games]
