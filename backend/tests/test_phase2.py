import pytest
import chess
from unittest.mock import patch, MagicMock
from config.settings import get_settings
from coach.schemas.models import Game, MoveAnalysis
from coach.analysis.classify import calculate_cpl_and_label
from coach.analysis.themes import classify_theme
from coach.analysis.pipeline import analyze_game

def test_cpl_and_label():
    settings = get_settings()
    
    # 1. Best move played -> CPL=0, label="ok"
    cpl, label = calculate_cpl_and_label(
        best_uci="e2e4",
        played_uci="e2e4",
        score_before=30,
        score_after=30,
        settings=settings
    )
    assert cpl == 0
    assert label == "ok"
    
    # 2. Slight inaccuracy
    cpl, label = calculate_cpl_and_label(
        best_uci="e2e4",
        played_uci="d2d4",
        score_before=30,
        score_after=-30,  # turn flipped: -(-30) = 30 -> loss of 30 - 30 = 0. Wait, if score_after is from opponent turn POV:
        # If score_before was 30 (our POV), and after playing opponent has -30 (opponent POV).
        # Our score is -(-30) = 30. Loss = 30 - 30 = 0.
        # Let's say opponent has 10 (opponent POV). Our POV is -10. Loss = 30 - (-10) = 40.
        settings=settings
    )
    # Let's check with direct score values
    # If S_best is 50 (mover POV), S_played is -20 (mover POV). Loss = 50 - (-20) = 70.
    # We will test calculate_cpl_and_label directly passing precalculated scores or before/after scores.
    # In classify.py, we will calculate:
    # S_best = score_before
    # S_played = -score_after
    # cpl = max(0, S_best - S_played)
    # Let's test this logic:
    # S_best = 30, score_after = 40 (opponent POV) -> S_played = -40 -> loss = 30 - (-40) = 70
    cpl, label = calculate_cpl_and_label("e2e4", "d2d4", 30, 40, settings)
    assert cpl == 70
    assert label == "inaccuracy"
    
    # 3. Mistake (loss of 150)
    # S_best = 50, score_after = 100 (opponent POV) -> S_played = -100 -> loss = 50 - (-100) = 150
    cpl, label = calculate_cpl_and_label("e2e4", "d2d4", 50, 100, settings)
    assert cpl == 150
    assert label == "mistake"
    
    # 4. Blunder (loss of 350)
    # S_best = 100, score_after = 250 (opponent POV) -> S_played = -250 -> loss = 350
    cpl, label = calculate_cpl_and_label("e2e4", "d2d4", 100, 250, settings)
    assert cpl == 350
    assert label == "blunder"


def test_classify_theme():
    # 1. Opening theme: ply <= 12
    board = chess.Board()
    assert classify_theme(board, ply=4, moved_piece_square=chess.E4) == "Opening"
    
    # 2. Pin theme: Pinned piece moved
    # Setup a pinned position: White King e1, White Knight e2, Black Rook e8
    board_pin = chess.Board(fen="4r3/8/8/8/8/8/4N3/4K3 w - - 0 1")
    # Knight on e2 is pinned to the King on e1
    assert classify_theme(board_pin, ply=20, moved_piece_square=chess.E2) == "Pin"
    
    # 3. Check theme: King put in check after move
    board_check = chess.Board()
    board_check.push_uci("f2f3") # White f3
    board_check.push_uci("e7e5") # Black e5
    board_check.push_uci("g2g4") # White g4
    board_check.push_uci("d8h4") # Black plays Qh4# (check)
    # Board is check
    assert classify_theme(board_check, ply=20, moved_piece_square=chess.H4) == "Check"

    # 4. Endgame theme: Non-pawn material count is small
    # King & Queen vs King & Queen
    board_endgame = chess.Board(fen="4k3/4q3/8/8/8/8/4Q3/4K3 w - - 0 1")
    assert classify_theme(board_endgame, ply=40, moved_piece_square=chess.E1) == "Endgame"

    # 5. Tactics theme: Middlegame default
    board_mid = chess.Board(fen="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
    assert classify_theme(board_mid, ply=15, moved_piece_square=chess.F3) == "Tactics"


@patch("coach.analysis.engine.Engine")
@patch("coach.utils.cache.get_cached_engine_eval")
def test_analyze_game_color_filtering(mock_get_cache, mock_engine_class):
    mock_get_cache.return_value = None
    mock_engine = MagicMock()
    mock_engine_class.from_settings.return_value = mock_engine
    mock_engine.__enter__.return_value = mock_engine

    from coach.schemas.models import EngineEval
    mock_engine.analyse_fen.side_effect = [
        EngineEval(best_uci="e2e4", pv_uci=["e2e4"], score_cp=30),
        EngineEval(best_uci="g1f3", pv_uci=["g1f3"], score_cp=35),
        EngineEval(best_uci="d7d6", pv_uci=["d7d6"], score_cp=-20),
    ]

    pgn = "1. e4 e5 2. Bc4 *"
    game = Game(
        game_id="g1",
        source="upload",
        pgn=pgn,
        white="user_player",
        black="opp_player",
        result="*",
        user_color="white"
    )
    
    settings = get_settings()
    analyses = analyze_game(game, settings)
    
    # We only analyze White's moves: ply 1 (e4) and ply 3 (Bc4).
    # Ply 2 (e5) is Black's move, so it is skipped because user_color == "white".
    assert len(analyses) == 2
    
    # First move: e4 (ply 1)
    assert analyses[0].ply == 1
    assert analyses[0].played_uci == "e2e4"
    assert analyses[0].centipawn_loss == 0
    assert analyses[0].label == "ok"
    
    # Second move: Bc4 (ply 3)
    assert analyses[1].ply == 3
    assert analyses[1].played_uci == "f1c4"
    # S_best = 35, S_played = -(-20) = 20. Loss = 35 - 20 = 15.
    assert analyses[1].centipawn_loss == 15
