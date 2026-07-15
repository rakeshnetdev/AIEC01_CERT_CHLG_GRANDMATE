import chess
import logging
from typing import List
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


def analyze_game(game: Game, settings: Settings) -> List[MoveAnalysis]:
    """Analyzes all plies of a game for the user's color, classifying mistakes."""
    from coach.tools.engine_eval import engine_eval
    logger.info(f"Starting analysis for game {game.game_id} (User color: {game.user_color})")
    
    analyses: List[MoveAnalysis] = []
    user_color_is_white = (game.user_color.lower() == "white")
    
    for ply, board_before, move in iter_positions(game):
        # Determine if this is a user move
        is_user_turn = board_before.turn == chess.WHITE if user_color_is_white else board_before.turn == chess.BLACK
        if not is_user_turn:
            continue
            
        played_uci = move.uci()
        fen_before = board_before.fen()
        
        # Get engine evaluation of the position before the move
        eval_before = engine_eval(fen_before, depth=settings.engine_depth)
        best_uci = eval_before.get("best_uci", "")
        best_san = ""
        if best_uci:
            try:
                best_san = board_before.san(chess.Move.from_uci(best_uci))
            except Exception:
                best_san = best_uci
                
        played_san = ""
        try:
            played_san = board_before.san(move)
        except Exception:
            played_san = played_uci
            
        # Optimization: if played move is the best move
        if played_uci == best_uci:
            cpl = 0
            label = "ok"
            theme = None
            eval_after_cp = eval_before.get("score_cp", 0)
            pv_san = get_pv_san(board_before, eval_before.get("pv_uci", []))
        else:
            # Player played a different move, evaluate the position after
            board_after = board_before.copy()
            board_after.push(move)
            fen_after = board_after.fen()
            
            eval_after = engine_eval(fen_after, depth=settings.engine_depth)
            eval_after_cp = eval_after.get("score_cp", 0)
            
            # Calculate CPL and assign label
            cpl, label = calculate_cpl_and_label(
                best_uci=best_uci,
                played_uci=played_uci,
                score_before=eval_before.get("score_cp", 0),
                score_after=eval_after_cp,
                settings=settings
            )
            
            # Classify theme if it's a mistake
            theme = None
            if label != "ok":
                # Check for Pin / Opening / Endgame on board_before
                theme = classify_theme(board_before, ply, move.from_square)
                # If no tactical theme was detected, check if the resulting move put opponent in check
                if theme == "Tactics":
                    theme_after = classify_theme(board_after, ply, move.to_square)
                    if theme_after == "Check":
                        theme = "Check"
            
            pv_san = get_pv_san(board_before, eval_before.get("pv_uci", []))
            
        # Append analysis
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
