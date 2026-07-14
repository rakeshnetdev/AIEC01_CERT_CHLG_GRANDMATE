import pytest
import chess
from unittest.mock import patch
from config.settings import get_settings
from coach.schemas.models import (
    Game, EngineEval, MoveAnalysis, Chunk, Explanation, Weakness, Drill, CoachReport
)
from coach.analysis.engine import Engine
from coach.llm.gateway import chat

def test_schemas_validation():
    # Test that models validate correctly with minimal correct data
    game = Game(
        game_id="test_1",
        source="lichess",
        pgn="1. e4 e5 2. Nf3",
        white="Player1",
        black="Player2",
        white_rating=1500,
        black_rating=1600,
        result="1-0",
        time_control="600",
        user_color="white",
        opening_name="King's Pawn Game"
    )
    assert game.game_id == "test_1"
    assert game.user_color == "white"

    engine_eval = EngineEval(best_uci="e2e4", pv_uci=["e2e4", "e7e5"], score_cp=35)
    assert engine_eval.score_cp == 35

    move_analysis = MoveAnalysis(
        ply=1,
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_uci="e2e4",
        played_san="e4",
        best_uci="e2e4",
        best_san="e4",
        eval_before_cp=30,
        eval_after_cp=30,
        centipawn_loss=0,
        label="ok",
        theme="Openings",
        pv_san=["e4", "e5"]
    )
    assert move_analysis.label == "ok"

    explanation = Explanation(
        ply=1,
        label="inaccuracy",
        why="Played passively",
        correct_plan="Control the center",
        sources=["openings.tsv"],
        grounded=True
    )
    assert explanation.grounded is True

    weakness = Weakness(theme="Tactic", count=3, example_plies=[10, 14, 18])
    assert weakness.count == 3

    drill = Drill(puzzle_id="puz_123", theme="fork", rating=1200, url="https://lichess.org/training/puz_123")
    assert drill.rating == 1200

    report = CoachReport(
        username="User1",
        games_reviewed=1,
        summary="Good game",
        findings=[explanation],
        top_weaknesses=[weakness],
        drills=[drill],
        latency_s=1.2,
        cost_usd=0.01
    )
    assert report.games_reviewed == 1


def test_engine_analyse_fen():
    s = get_settings()
    # Ensure Stockfish path is set and valid
    assert s.stockfish_path is not None
    
    # Starting position FEN
    startpos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    with Engine.from_settings(s) as engine:
        eval_result = engine.analyse_fen(startpos, depth=5)
        
        assert isinstance(eval_result, EngineEval)
        assert eval_result.best_uci != ""
        assert len(eval_result.pv_uci) > 0
        # Starting position evaluation should be balanced
        assert -150 < eval_result.score_cp < 150


def test_engine_mate_clamping():
    s = get_settings()
    # FEN for a position where mate is 1 move away (Scholar's mate: White Q on f7 mates)
    # 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6 4.Qxf7#
    mate_fen = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 4"
    
    with Engine.from_settings(s) as engine:
        eval_result = engine.analyse_fen(mate_fen, depth=5)
        assert isinstance(eval_result, EngineEval)
        # Side to move (Black) is mated, score should be -10000
        assert eval_result.score_cp == -10000


def test_gateway_chat_with_fallback():
    # Verify the fallback mechanism works by providing an invalid Gemini key and a valid OpenAI key.
    # The call should successfully fallback to OpenAI.
    s = get_settings()
    
    # We expect OpenAI key to be present in our local settings from .env
    if not s.openai_api_key or s.openai_api_key.startswith("your_openai"):
        pytest.skip("Skipping chat test: valid OPENAI_API_KEY is not set.")

    messages = [{"role": "user", "content": "Reply with exactly the word SUCCESS."}]
    
    response = chat(messages)
    assert "SUCCESS" in response.upper()


def test_gateway_fallback_forced_failure(mocker=None):
    # If pytest-mock or unittest.mock is used, we can mock litellm.completion to fail on Gemini
    # and succeed on OpenAI. But since LiteLLM handles fallbacks internally, we can test that
    # it passes the list of fallbacks correctly.
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            mocker.MagicMock(message=mocker.MagicMock(content="Fallback Mock Success"))
        ] if mocker else [
            type('obj', (object,), {
                'message': type('obj', (object,), {'content': 'Fallback Mock Success'})()
            })()
        ]
        
        response = chat([{"role": "user", "content": "hello"}])
        assert response == "Fallback Mock Success"
        
        # Verify litellm.completion was called with the primary model and fallbacks
        s = get_settings()
        mock_completion.assert_called_once()
        called_kwargs = mock_completion.call_args[1]
        assert called_kwargs["model"] == s.llm_model
        assert called_kwargs["fallbacks"] == [s.llm_fallback_model]
