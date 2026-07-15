import json
import os
import sys
import chess
from pathlib import Path

# Add backend src folder to python path so we can import from config and coach
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from config.settings import get_settings
from coach.analysis.engine import Engine
from coach.analysis.classify import calculate_cpl_and_label

# A set of test positions and moves (some good, some bad) to analyze
TEST_POSITIONS = [
    # 1. Starting position - standard e4
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "played": "e2e4",
        "description": "Standard opening move"
    },
    # 2. Starting position - rare/passive a4
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "played": "a2a4",
        "description": "Passive opening move"
    },
    # 3. Scholar's mate threat ignored (blunder)
    {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
        "played": "h7h6",
        "description": "Ignoring checkmate threat on f7 (blunder)"
    },
    # 4. Scholar's mate threat defended (ok)
    {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
        "played": "g7g6",
        "description": "Defending checkmate threat with g6 (ok)"
    },
    # 5. Hanging a full knight in Italian Game (blunder)
    {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        "played": "g8f6",
        "description": "Two Knights defense (ok)"
    },
    # 6. Hanging piece: playing a random blunder e5e4 hanging pawn (blunder/mistake)
    {
        "fen": "r1bqkbnr/ppp2ppp/2np4/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4",
        "played": "f3e5",
        "description": "Hanging knight by capturing defended pawn (blunder)"
    },
    # 7. Symmetrical position, trading queens (ok)
    {
        "fen": "r3k2r/ppq2ppp/2nbbn2/3pp3/3PP3/3BBN2/PPQ2PPP/R3K2R w KQkq - 4 10",
        "played": "d4e5",
        "description": "Natural pawn center trade (ok)"
    },
    # 8. Endgame position: King and Pawn endgame (inaccuracy/mistake)
    {
        "fen": "8/8/8/8/p7/k7/P7/K7 w - - 0 1",
        "played": "a1b1",
        "description": "Standard king move in simple endgame (ok)"
    },
    # 9. Middlegame tactical pin (ok vs blunder)
    {
        "fen": "r1b1k2r/ppq2ppp/2nbpn2/3p4/3PP3/P1NB1N2/1PQ2PPP/R1B1K2R w KQkq - 1 9",
        "played": "e4e5",
        "description": "Forking knight and bishop (ok)"
    }
]

def main():
    settings = get_settings()
    # Ensure correct Stockfish path is available
    if not os.path.exists(settings.stockfish_path):
        import shutil
        sys_stockfish = shutil.which("stockfish")
        if sys_stockfish:
            settings.stockfish_path = sys_stockfish

    print(f"Generating synthetic dataset using engine: {settings.stockfish_path}")
    
    dataset = []
    
    with Engine.from_settings(settings) as engine:
        for idx, pos in enumerate(TEST_POSITIONS):
            fen = pos["fen"]
            played = pos["played"]
            
            # Analyze position before
            eval_before = engine.analyse_fen(fen, depth=settings.engine_depth)
            
            # Simulate play
            board = chess.Board(fen)
            move = chess.Move.from_uci(played)
            
            if move not in board.legal_moves:
                print(f"Warning: Move {played} is illegal in FEN {fen}. Skipping.")
                continue
                
            board.push(move)
            fen_after = board.fen()
            
            # Analyze position after
            eval_after = engine.analyse_fen(fen_after, depth=settings.engine_depth)
            
            # Calculate CPL and Label
            cpl, label = calculate_cpl_and_label(
                best_uci=eval_before.best_uci,
                played_uci=played,
                score_before=eval_before.score_cp,
                score_after=eval_after.score_cp,
                settings=settings
            )
            
            dataset.append({
                "id": idx + 1,
                "fen_before": fen,
                "played_uci": played,
                "description": pos["description"],
                "expected_best_uci": eval_before.best_uci,
                "expected_cpl": cpl,
                "expected_label": label,
                "score_before": eval_before.score_cp,
                "score_after": eval_after.score_cp
            })
            
    # Output to evals folder
    evals_dir = ROOT / "evals"
    evals_dir.mkdir(exist_ok=True)
    
    output_file = evals_dir / "synthetic_dataset.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
        
    print(f"Successfully generated {len(dataset)} labeled positions at: {output_file}")

if __name__ == "__main__":
    main()
