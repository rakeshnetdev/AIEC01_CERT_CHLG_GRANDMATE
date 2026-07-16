import chess
import logging
from typing import List, Optional
from config.settings import Settings
from coach.schemas.models import Game, MoveAnalysis
from coach.ingestion.pgn import iter_positions
from coach.analysis.classify import calculate_cpl_and_label
from coach.analysis.themes import classify_theme

logger = logging.getLogger(__name__)

def get_pv_san(board: chess.Board, pv_uci: List[str]) -> List[str]:
    """Helper to convert a list of UCI moves into SAN moves relative to the board state."""
    temp_board = board.copy()
    pv_san = []
    for uci in pv_uci:
        try:
            m = chess.Move.from_uci(uci)
            if m in temp_board.legal_moves:
                pv_san.append(temp_board.san(m))
                temp_board.push(m)
            else:
                break
        except Exception:
            break
    return pv_san


def _is_user_turn(board_before: chess.Board, user_color_is_white: bool) -> bool:
    """Helper to check if it is the user's turn to move."""
    return board_before.turn == chess.WHITE if user_color_is_white else board_before.turn == chess.BLACK


def _get_move_san(board: chess.Board, move: chess.Move, fallback_uci: str) -> str:
    """Safely converts a chess Move to SAN notation, falling back to UCI on error."""
    try:
        return board.san(move)
    except Exception:
        return fallback_uci


def _classify_tactical_theme(board_before: chess.Board, board_after: chess.Board, ply: int, move: chess.Move, label: str) -> Optional[str]:
    """Identifies the tactical theme associated with a mistake or blunder."""
    if label == "ok":
        return None
        
    # Check for Pin / Opening / Endgame on the starting board state
    theme = classify_theme(board_before, ply, move.from_square)
    
    # If generic 'Tactics' was returned, check if the resulting move checked the opponent
    if theme == "Tactics":
        theme_after = classify_theme(board_after, ply, move.to_square)
        if theme_after == "Check":
            return "Check"
            
    return theme


def analyze_game(game: Game, settings: Settings) -> List[MoveAnalysis]:
    """Analyzes all plies of a game for the user's color, classifying mistakes."""
    from coach.analysis.engine import Engine
    from coach.utils.cache import get_cached_engine_eval, cache_engine_eval

    logger.info(f"Starting analysis for game {game.game_id} (User color: {game.user_color})")
    
    analyses: List[MoveAnalysis] = []
    user_color_is_white = (game.user_color.lower() == "white")
    
    with Engine.from_settings(settings) as engine:
        def get_eval(fen: str) -> dict:
            # Try reading from cache
            cached = get_cached_engine_eval(fen, settings.engine_depth)
            if cached:
                return cached
                
            # Miss: Run the Stockfish engine
            eval_result = engine.analyse_fen(fen, depth=settings.engine_depth)
            
            # Cache the new result
            cache_engine_eval(
                fen=fen,
                depth=settings.engine_depth,
                best_uci=eval_result.best_uci,
                pv_uci=eval_result.pv_uci,
                score_cp=eval_result.score_cp
            )
            return eval_result.model_dump()

        for ply, board_before, move in iter_positions(game):
            # Check if this is the user's move
            if not _is_user_turn(board_before, user_color_is_white):
                continue
                
            played_uci = move.uci()
            fen_before = board_before.fen()
            
            # Get engine evaluation of the position before the move
            eval_before = get_eval(fen_before)
            best_uci = eval_before.get("best_uci", "")
            
            # Formats SAN moves
            best_san = _get_move_san(board_before, chess.Move.from_uci(best_uci) if best_uci else chess.Move.null(), best_uci)
            played_san = _get_move_san(board_before, move, played_uci)
                
            # Evaluate the position after the played move
            board_after = board_before.copy()
            board_after.push(move)
            
            if played_uci == best_uci:
                # Played best move
                cpl = 0
                label = "ok"
                theme = None
                eval_after_cp = eval_before.get("score_cp", 0)
            else:
                # Played a different move, calculate centipawn loss and class
                eval_after = get_eval(board_after.fen())
                eval_after_cp = eval_after.get("score_cp", 0)
                
                cpl, label = calculate_cpl_and_label(
                    best_uci=best_uci,
                    played_uci=played_uci,
                    score_before=eval_before.get("score_cp", 0),
                    score_after=eval_after_cp,
                    settings=settings
                )
                theme = _classify_tactical_theme(board_before, board_after, ply, move, label)
                
            pv_san = get_pv_san(board_before, eval_before.get("pv_uci", []))
            
            # Append analysis record
            analyses.append(
                MoveAnalysis(
                    ply=ply,
                    fen_before=fen_before,
                    played_uci=played_uci,
                    played_san=played_san,
                    best_uci=best_uci,
                    best_san=best_san,
                    eval_before_cp=eval_before.get("score_cp", 0),
                    eval_after_cp=eval_after_cp,
                    centipawn_loss=cpl,
                    label=label,
                    theme=theme,
                    pv_san=pv_san
                )
            )
            
    return analyses
