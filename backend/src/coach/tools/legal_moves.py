import chess
import logging
from typing import List

logger = logging.getLogger(__name__)

def legal_moves(fen: str) -> List[str]:
    """Agent tool that returns a list of legal moves in UCI format for a given FEN string."""
    try:
        board = chess.Board(fen)
        return [move.uci() for move in board.legal_moves]
    except Exception as e:
        logger.error(f"Error checking legal moves for FEN {fen}: {e}")
        return []
