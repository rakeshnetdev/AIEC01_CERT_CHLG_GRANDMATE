"""Synthetic evaluation dataset generator for Grandmate.

Design principle (see final_docs/synthetic_data_and_eval_design.md):

    Ground truth MUST originate outside the code being graded.

The previous version of this file labelled every position by calling the production
classifier ``calculate_cpl_and_label``; ``report.py`` then "graded" the system by calling
that same pure function on the same stored inputs. Comparing a deterministic function to
itself always yields 100%, so Detection F1 / Severity Accuracy were guaranteed by
construction and could not fail.

This generator therefore:

  1. **Never imports the production classifier.** Labels come from an independent
     *oracle*: Stockfish run at a much greater depth than production, combined with a
     reference implementation of the CPL/severity rule written here from the spec.
  2. **Generates rather than hardcodes.** For each base position it enumerates candidate
     legal moves and measures each one, so every severity class is discovered empirically
     (including threshold-boundary cases) instead of being asserted by hand.
  3. **Covers the scenario matrix** — severity class x game phase x side to move x
     nature, plus the edge cases that break naive implementations (promotion, castling,
     en passant, forced mate, stalemate, SAN disambiguation).

What this measures once ``report.py`` consumes it: *does the production configuration
(depth = ``settings.engine_depth``, thresholds from settings) approximate the deeper
oracle?* That is a real question with a real failure mode.

Usage:
    cd backend && uv run python ../evals/generate_synthetic.py [--oracle-depth N] [--max-candidates N]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import chess

# Add backend src folder to python path so we can import from config and coach
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from config.settings import get_settings
from coach.analysis.engine import Engine

# NOTE: coach.analysis.classify is deliberately NOT imported. Importing the function under
# test to build its own ground truth is exactly the circularity this module exists to fix.


# --------------------------------------------------------------------------------------
# Reference implementation of the severity rule (the "spec"), independent of production.
# --------------------------------------------------------------------------------------

def reference_cpl(best_uci: str, played_uci: str, score_before: int, score_after: int) -> int:
    """Centipawn loss, implemented from the spec rather than imported from production.

    Both scores are side-to-move relative. ``score_after`` is negated because the turn
    flips after the move, so it is expressed from the opponent's point of view.
    """
    if best_uci == played_uci:
        return 0
    played_from_mover_pov = -score_after
    return max(0, score_before - played_from_mover_pov)


def reference_label(cpl: int, inaccuracy_cp: int, mistake_cp: int, blunder_cp: int) -> str:
    """Severity band for a centipawn loss. Thresholds are half-open: [0, inaccuracy) = ok."""
    if cpl < inaccuracy_cp:
        return "ok"
    if cpl < mistake_cp:
        return "inaccuracy"
    if cpl < blunder_cp:
        return "mistake"
    return "blunder"


# --------------------------------------------------------------------------------------
# Scenario matrix: base positions to generate candidate moves from.
# --------------------------------------------------------------------------------------
# Each base position contributes many dataset rows (one per candidate move measured), so
# severity coverage emerges from measurement instead of being hand-asserted.

BASE_POSITIONS: List[Dict] = [
    # ---- Opening ---------------------------------------------------------------------
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "phase": "opening", "nature": "positional",
        "description": "Standard starting position, White to move",
    },
    {
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "phase": "opening", "nature": "positional",
        "description": "After 1.e4, Black to move",
    },
    {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
        "phase": "opening", "nature": "tactical",
        "description": "Scholar's mate threat on f7, Black to move (must defend)",
    },
    {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        "phase": "opening", "nature": "positional",
        "description": "Italian Game, Black to move",
    },
    # ---- Middlegame ------------------------------------------------------------------
    {
        "fen": "r1b1k2r/ppq2ppp/2nbpn2/3p4/3PP3/P1NB1N2/1PQ2PPP/R1B1K2R w KQkq - 1 9",
        "phase": "middlegame", "nature": "tactical",
        "description": "Central tension, White to move, castling rights both sides",
    },
    {
        "fen": "r3k2r/ppq2ppp/2nbbn2/3pp3/3PP3/3BBN2/PPQ2PPP/R3K2R b KQkq - 4 10",
        "phase": "middlegame", "nature": "positional",
        "description": "Symmetrical middlegame, Black to move, castling available",
    },
    {
        "fen": "r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 6 6",
        "phase": "middlegame", "nature": "positional",
        "description": "Quiet Italian middlegame, both sides castled, White to move",
    },
    # ---- Endgame ---------------------------------------------------------------------
    {
        "fen": "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1",
        "phase": "endgame", "nature": "positional",
        "description": "King and pawn endgame, White to move (opposition matters)",
    },
    {
        "fen": "8/8/8/4k3/8/8/4P3/4K2R b K - 0 1",
        "phase": "endgame", "nature": "positional",
        "description": "Rook and pawn vs bare king, Black to move",
    },
    {
        "fen": "6k1/5ppp/8/8/8/8/5PPP/R5K1 b - - 0 1",
        "phase": "endgame", "nature": "tactical",
        "description": "Back-rank motif, Black to move (king has no luft)",
    },
]

# Edge cases that break naive implementations. Tagged so report.py can slice them out.
EDGE_CASE_POSITIONS: List[Dict] = [
    {
        "fen": "8/P6k/8/8/8/8/8/K7 w - - 0 1",
        "phase": "endgame", "nature": "tactical", "edge": "promotion",
        "description": "Pawn on a7 promoting; includes underpromotion candidates",
    },
    {
        "fen": "r3k2r/ppp2ppp/2n1bn2/3pp3/3PP3/2N1BN2/PPP2PPP/R3K2R w KQkq - 6 8",
        "phase": "middlegame", "nature": "positional", "edge": "castling",
        "description": "Both castlings legal for White (O-O and O-O-O)",
    },
    {
        "fen": "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 4",
        "phase": "opening", "nature": "tactical", "edge": "en_passant",
        "description": "En passant capture exf6 available",
    },
    {
        "fen": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
        "phase": "endgame", "nature": "tactical", "edge": "forced_mate",
        "description": "Mate in one available (Ra8#); score_cp is a mate score, not centipawns",
    },
    {
        "fen": "7k/5Q2/8/8/8/8/8/K7 w - - 0 1",
        "phase": "endgame", "nature": "tactical", "edge": "stalemate_trap",
        "description": "Careless queen moves stalemate Black instead of mating",
    },
    {
        "fen": "4k3/8/8/8/8/1N3N2/8/4K3 w - - 0 1",
        "phase": "endgame", "nature": "positional", "edge": "san_disambiguation",
        "description": "Two knights can reach d2/d4 — forces SAN file disambiguation (Nbd2 vs Nfd2)",
    },
]


def _candidate_moves(board: chess.Board, best_uci: str, cap: int) -> List[chess.Move]:
    """Pick a deterministic, spread-out set of legal moves to measure.

    Always includes the engine's best move (so the 'ok' class is reachable) and then walks
    the remaining legal moves in a stable order, sampling evenly across the list so we get
    a spread of quality rather than only the first few alphabetically.
    """
    legal = sorted(board.legal_moves, key=lambda m: m.uci())
    picked: List[chess.Move] = []

    best = next((m for m in legal if m.uci() == best_uci), None)
    if best is not None:
        picked.append(best)

    rest = [m for m in legal if m.uci() != best_uci]
    if not rest:
        return picked

    slots = max(0, cap - len(picked))
    if slots >= len(rest):
        picked.extend(rest)
    else:
        # Even stride across the sorted list keeps selection deterministic and spread.
        stride = len(rest) / slots
        picked.extend(rest[int(i * stride)] for i in range(slots))
    return picked


def _measure_position(engine: Engine, base: Dict, depth: int, cap: int,
                      thresholds: Dict[str, int], start_id: int) -> List[Dict]:
    """Measure every candidate move in one base position with the deep oracle."""
    fen = base["fen"]
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        print(f"  !! invalid FEN, skipping: {fen} ({exc})")
        return []
    if not board.is_valid():
        print(f"  !! illegal position, skipping: {fen}")
        return []
    if board.is_game_over():
        print(f"  !! position is already terminal, skipping: {fen}")
        return []

    eval_before = engine.analyse_fen(fen, depth=depth)
    side = "white" if board.turn == chess.WHITE else "black"
    rows: List[Dict] = []

    for move in _candidate_moves(board, eval_before.best_uci, cap):
        after = board.copy()
        san = after.san(move)
        after.push(move)

        # A move that ends the game leaves no side-to-move evaluation to compare against,
        # so CPL is not well defined. Keep mate-delivering moves (they are the point of the
        # forced_mate scenario) but record them explicitly.
        terminal = after.is_game_over()
        eval_after = engine.analyse_fen(after.fen(), depth=depth)

        cpl = reference_cpl(eval_before.best_uci, move.uci(),
                            eval_before.score_cp, eval_after.score_cp)
        label = reference_label(cpl, thresholds["inaccuracy"],
                               thresholds["mistake"], thresholds["blunder"])

        rows.append({
            "id": start_id + len(rows),
            # --- the position under test -------------------------------------------
            "fen_before": fen,
            "fen_after": after.fen(),
            "played_uci": move.uci(),
            "played_san": san,
            # --- scenario metadata (lets report.py slice results) -------------------
            "phase": base["phase"],
            "side_to_move": side,
            "nature": base["nature"],
            "edge": base.get("edge"),
            "description": base["description"],
            "terminal_after_move": terminal,
            # --- ground truth, from the independent oracle --------------------------
            "oracle_depth": depth,
            "oracle_best_uci": eval_before.best_uci,
            "oracle_score_before": eval_before.score_cp,
            "oracle_score_after": eval_after.score_cp,
            "oracle_cpl": cpl,
            "expected_label": label,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Grandmate's synthetic eval dataset.")
    parser.add_argument("--oracle-depth", type=int, default=None,
                        help="Stockfish depth for ground truth. Must exceed production depth. "
                             "Default: production depth + 8 (min 24).")
    parser.add_argument("--max-candidates", type=int, default=10,
                        help="Max candidate moves measured per base position (default: 10).")
    args = parser.parse_args()

    settings = get_settings()

    # Ensure a usable Stockfish binary
    if not os.path.exists(settings.stockfish_path):
        import shutil
        sys_stockfish = shutil.which("stockfish")
        if sys_stockfish:
            settings.stockfish_path = sys_stockfish
        else:
            raise SystemExit(f"Stockfish not found at {settings.stockfish_path} and not on PATH.")

    production_depth = settings.engine_depth
    oracle_depth = args.oracle_depth or max(production_depth + 8, 24)
    if oracle_depth <= production_depth:
        raise SystemExit(
            f"Oracle depth ({oracle_depth}) must exceed production depth ({production_depth}); "
            "otherwise the 'ground truth' is no stronger than the system under test."
        )

    thresholds = {
        "inaccuracy": settings.inaccuracy_cp,
        "mistake": settings.mistake_cp,
        "blunder": settings.blunder_cp,
    }

    print(f"Engine          : {settings.stockfish_path}")
    print(f"Oracle depth    : {oracle_depth}  (production depth = {production_depth})")
    print(f"Thresholds (cp) : {thresholds}")
    print(f"Base positions  : {len(BASE_POSITIONS)} + {len(EDGE_CASE_POSITIONS)} edge cases")
    print("Measuring candidate moves with the deep oracle — this takes a few minutes...\n")

    dataset: List[Dict] = []
    with Engine.from_settings(settings) as engine:
        for base in BASE_POSITIONS + EDGE_CASE_POSITIONS:
            tag = base.get("edge") or f"{base['phase']}/{base['nature']}"
            print(f"  [{tag}] {base['description']}")
            rows = _measure_position(engine, base, oracle_depth, args.max_candidates,
                                     thresholds, start_id=len(dataset) + 1)
            dataset.extend(rows)
            counts: Dict[str, int] = {}
            for r in rows:
                counts[r["expected_label"]] = counts.get(r["expected_label"], 0) + 1
            print(f"      -> {len(rows)} rows {counts}")

    evals_dir = ROOT / "evals"
    evals_dir.mkdir(exist_ok=True)
    output_file = evals_dir / "synthetic_dataset.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    # ---- Coverage summary ------------------------------------------------------------
    def tally(key: str) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for row in dataset:
            k = str(row.get(key))
            out[k] = out.get(k, 0) + 1
        return out

    print("\n" + "=" * 62)
    print("  SYNTHETIC DATASET COVERAGE")
    print("=" * 62)
    print(f"Total rows      : {len(dataset)}")
    print(f"By severity     : {tally('expected_label')}")
    print(f"By phase        : {tally('phase')}")
    print(f"By side to move : {tally('side_to_move')}")
    print(f"By nature       : {tally('nature')}")
    print(f"Edge cases      : { {k: v for k, v in tally('edge').items() if k != 'None'} }")

    missing = {"ok", "inaccuracy", "mistake", "blunder"} - set(tally("expected_label"))
    if missing:
        print(f"\nWARNING: no rows generated for severity class(es): {sorted(missing)}. "
              "Add base positions that elicit them, or raise --max-candidates.")
    if "black" not in tally("side_to_move"):
        print("\nWARNING: no black-to-move rows — the old harness silently dropped these.")

    print("=" * 62)
    print(f"Saved {len(dataset)} labelled positions to: {output_file}")


if __name__ == "__main__":
    main()
