import sys
import re
import chess
import pytest
from pathlib import Path

# Add backend src folder to python path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from config.settings import get_settings
from coach.agent.graph import compile_coach_graph
from coach.schemas.models import Game

def load_dataset():
    import json
    dataset_file = ROOT / "evals" / "synthetic_dataset.json"
    if not dataset_file.exists():
        pytest.skip("synthetic_dataset.json does not exist. Run generate_synthetic.py first.")
    with open(dataset_file, "r", encoding="utf-8") as f:
        return json.load(f)

# Regex to find SAN moves in text (e.g. e4, Nf3, Qh4#, O-O, Bxf7+)
SAN_REGEX = re.compile(r'\b(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:\=[QRBN])?[+#]?|O-O-O|O-O)\b')

def test_illegal_move_rate():
    dataset = load_dataset()
    app = compile_coach_graph()
    
    total_moves_checked = 0
    illegal_moves = 0
    
    for item in dataset[:3]:
        fen = item["fen_before"]
        played = item["played_uci"]
        
        # Build a single-position PGN and analyze it
        board = chess.Board(fen)
        move = chess.Move.from_uci(played)
        san_played = board.san(move)
        
        game = Game(
            game_id="eval_g",
            source="upload",
            pgn=f"1. {san_played} *",
            white="White",
            black="Black",
            result="*",
            user_color="white" if board.turn == chess.WHITE else "black"
        )
        
        inputs = {
            "game": game,
            "messages": []
        }
        config = {"configurable": {"thread_id": "eval_thread"}}
        output_state = app.invoke(inputs, config)
        narration = output_state.get("output", "")
        
        moves_found = SAN_REGEX.findall(narration)
        board_before = chess.Board(fen)
        board_after = board_before.copy()
        board_after.push(move)
        
        all_legal_moves_san = {board_before.san(m) for m in board_before.legal_moves} | \
                              {board_after.san(m) for m in board_after.legal_moves}
                              
        squares = {chess.square_name(sq) for sq in chess.SQUARES}
        
        for m_str in moves_found:
            if m_str in squares:
                continue
            total_moves_checked += 1
            if m_str not in all_legal_moves_san:
                print(f"Illegal/Hallucinated move detected: '{m_str}'")
                illegal_moves += 1
                
    illegal_rate = illegal_moves / total_moves_checked if total_moves_checked > 0 else 0.0
    print(f"\nGrounding Metrics:")
    print(f"Total moves checked: {total_moves_checked}, Illegal moves: {illegal_moves}")
    assert illegal_rate == 0.0
