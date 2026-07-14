import logging
from typing import Dict, Any
from config.settings import get_settings
from coach.analysis.engine import Engine
from coach.utils.cache import get_cached_engine_eval, cache_engine_eval

logger = logging.getLogger(__name__)

def engine_eval(fen: str, depth: int) -> Dict[str, Any]:
    """Agent tool that performs evaluation of a chess FEN position.
    
    Checks database cache first, runs Stockfish if not found.
    Returns a dict representation of EngineEval.
    """
    logger.info(f"engine_eval tool called for FEN at depth {depth}")
    
    # Try reading from cache
    cached = get_cached_engine_eval(fen, depth)
    if cached:
        logger.info("Engine eval cache HIT.")
        return cached
        
    logger.info("Engine eval cache MISS. Running Stockfish...")
    settings = get_settings()
    
    try:
        with Engine.from_settings(settings) as engine:
            eval_result = engine.analyse_fen(fen, depth=depth)
            
            # Cache the new result
            cache_engine_eval(
                fen=fen,
                depth=depth,
                best_uci=eval_result.best_uci,
                pv_uci=eval_result.pv_uci,
                score_cp=eval_result.score_cp
            )
            
            return eval_result.model_dump()
    except Exception as e:
        logger.error(f"Stockfish engine evaluation failed: {e}")
        # Return a safe fallback
        return {
            "best_uci": "",
            "pv_uci": [],
            "score_cp": 0
        }
