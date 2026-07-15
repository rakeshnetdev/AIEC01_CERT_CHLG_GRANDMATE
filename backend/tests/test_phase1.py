import pytest
import json
import chess
import chess.pgn
import io
import sqlite3
from unittest.mock import patch, MagicMock
from coach.schemas.models import Game
from coach.ingestion.pgn import parse_pgn, iter_positions
from coach.ingestion.lichess import fetch_lichess_games
from coach.ingestion.chesscom import fetch_chesscom_games
from coach.tools.fetch_games import fetch_games
from coach.tools.legal_moves import legal_moves
from coach.tools.engine_eval import engine_eval
from coach.utils.cache import get_cache_db, cache_http_response, get_cached_http_response, cache_engine_eval, get_cached_engine_eval
from config.settings import get_settings

# --- Ingestion & Parsing Tests ---

def test_parse_pgn_normal():
    pgn_data = """[Event "Casual Game"]
[Site "https://lichess.org/test"]
[Date "2026.07.14"]
[Round "-"]
[White "magnus"]
[Black "hikaru"]
[Result "1-0"]
[UTCDate "23:44:00"]
[Opening "King's Pawn Game"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 *"""
    
    # Check that white is inferred as user when username is magnus
    game_white = parse_pgn(pgn_data, "upload", "magnus")
    assert game_white.user_color == "white"
    assert game_white.white == "magnus"
    assert game_white.black == "hikaru"
    assert game_white.opening_name == "King's Pawn Game"
    
    # Check that black is inferred as user when username is hikaru
    game_black = parse_pgn(pgn_data, "upload", "hikaru")
    assert game_black.user_color == "black"

    # Default to white if username doesn't match either
    game_default = parse_pgn(pgn_data, "upload", "other_player")
    assert game_default.user_color == "white"


def test_iter_positions():
    pgn_data = """[Event "Casual Game"]
1. e4 e5 2. Nf3 Nc6 *"""
    game = parse_pgn(pgn_data, "upload", "magnus")
    
    positions = list(iter_positions(game))
    # 4 plies: e4, e5, Nf3, Nc6
    assert len(positions) == 4
    
    # First position (ply 1, white's first move: e4)
    ply, board_before, move = positions[0]
    assert ply == 1
    assert board_before.fen() == chess.Board().fen()
    assert move.uci() == "e2e4"
    
    # Second position (ply 2, black's response: e5)
    ply2, board_before2, move2 = positions[1]
    assert ply2 == 2
    board_test = chess.Board()
    board_test.push_uci("e2e4")
    assert board_before2.fen() == board_test.fen()
    assert move2.uci() == "e7e5"


# --- HTTP Fetcher Mock Tests ---

@patch("httpx.get")
def test_fetch_lichess_games_mock(mock_get):
    # Mock return NDJSON games
    ndjson_content = (
        '{"id":"g1","players":{"white":{"user":{"name":"magnus"}},"black":{"user":{"name":"hikaru"}}},"winner":"white","moves":"e4 e5 Nf3 Nc6","speed":"blitz","opening":{"name":"Open Ruy Lopez"}}\n'
        '{"id":"g2","players":{"white":{"user":{"name":"hikaru"}},"black":{"user":{"name":"magnus"}}},"winner":"white","moves":"d4 d5 c4","speed":"blitz"}\n'
    )
    mock_get.return_value = MagicMock(status_code=200, text=ndjson_content)
    
    games = fetch_lichess_games("magnus", max_games=2)
    assert len(games) == 2
    assert games[0].game_id == "g1"
    assert games[0].user_color == "white"
    assert games[1].game_id == "g2"
    assert games[1].user_color == "black"


@patch("httpx.get")
def test_fetch_chesscom_games_mock(mock_get):
    # Mock return list of games by month
    games_json = {
        "games": [
            {
                "url": "https://www.chess.com/game/live/1",
                "pgn": '[White "magnus"]\n[Black "hikaru"]\n[Result "1-0"]\n\n1. e4 e5 *',
                "white": {"username": "magnus"},
                "black": {"username": "hikaru"},
                "time_class": "blitz"
            }
        ]
    }
    
    # First mock return 429 once, then 200 to test backoff/retry
    response_429 = MagicMock(status_code=429, headers={"Retry-After": "1"})
    response_200 = MagicMock(status_code=200, text=json.dumps(games_json))
    
    mock_get.side_effect = [response_429, response_200]
    
    games = fetch_chesscom_games("magnus", months=1, max_games=1)
    assert len(games) == 1
    assert games[0].white == "magnus"
    assert games[0].user_color == "white"


# --- Caching Tests ---

def test_sqlite_caching(tmp_path):
    # Use a temporary database for testing cache
    db_file = str(tmp_path / "test_cache.db")
    
    # 1. HTTP Cache Test
    url = "https://lichess.org/api/games/user/test_user"
    response_text = "some raw data"
    
    # Initially cache should be empty
    assert get_cached_http_response(url, db_path=db_file) is None
    
    # Cache response
    cache_http_response(url, response_text, db_path=db_file)
    
    # Now it should retrieve successfully
    assert get_cached_http_response(url, db_path=db_file) == response_text

    # 2. Engine Cache Test
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    depth = 12
    best_uci = "e2e4"
    pv_uci = ["e2e4", "e7e5"]
    score_cp = 35
    
    # Initially cache should be empty
    assert get_cached_engine_eval(fen, depth, db_path=db_file) is None
    
    # Cache evaluation
    cache_engine_eval(fen, depth, best_uci, pv_uci, score_cp, db_path=db_file)
    
    # Retrieve evaluation
    cached = get_cached_engine_eval(fen, depth, db_path=db_file)
    assert cached is not None
    assert cached["best_uci"] == best_uci
    assert cached["pv_uci"] == pv_uci
    assert cached["score_cp"] == score_cp


# --- Tools Tests ---

def test_legal_moves_tool():
    startpos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    moves = legal_moves(startpos)
    assert "e2e4" in moves
    assert "d2d4" in moves
    assert "e7e5" not in moves  # Illegal for White first move


@patch("coach.tools.engine_eval.Engine")
def test_engine_eval_tool(mock_engine_cls):
    from coach.schemas.models import EngineEval
    mock_instance = MagicMock()
    mock_instance.analyse_fen.return_value = EngineEval(best_uci="e2e4", pv_uci=["e2e4"], score_cp=35)
    mock_engine_cls.from_settings.return_value = mock_instance
    mock_instance.__enter__.return_value = mock_instance
    
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    result = engine_eval(fen, depth=5)
    assert result["best_uci"] == "e2e4"
    assert result["score_cp"] == 35
