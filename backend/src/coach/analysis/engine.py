import chess
import chess.engine
from typing import Optional
from config.settings import Settings
from coach.schemas.models import EngineEval

class Engine:
    def __init__(self, stockfish_path: str, default_depth: int = 16):
        self.stockfish_path = stockfish_path
        self.default_depth = default_depth
        self._engine: Optional[chess.engine.SimpleEngine] = None

    @classmethod
    def from_settings(cls, s: Settings) -> "Engine":
        return cls(stockfish_path=s.stockfish_path, default_depth=s.engine_depth)

    def __enter__(self) -> "Engine":
        self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None

    def analyse_fen(self, fen: str, depth: int | None = None) -> EngineEval:
        if not self._engine:
            raise RuntimeError("Engine is not initialized. Use context manager or call __enter__.")

        board = chess.Board(fen)
        d = depth or self.default_depth

        info = self._engine.analyse(board, chess.engine.Limit(depth=d))

        # Extract principal variation (PV)
        pv = info.get("pv", [])
        pv_uci = [m.uci() for m in pv]

        if pv_uci:
            best_uci = pv_uci[0]
        else:
            # Fallback if PV is empty
            play_result = self._engine.play(board, chess.engine.Limit(depth=d))
            best_move = play_result.move
            best_uci = best_move.uci() if best_move else ""
            pv_uci = [best_uci] if best_uci else []

        # Extract score relative to the side to move (board.turn)
        pov_score = info["score"].pov(board.turn)
        if pov_score.is_mate():
            mate_moves = pov_score.mate()
            # If mate_moves is positive, the side to move is winning (mating)
            # If negative, the side to move is losing (being mated)
            if mate_moves > 0:
                score_cp = 10000
            else:
                score_cp = -10000
        else:
            score_cp = pov_score.score()
            if score_cp is None:
                score_cp = 0
            # Ensure CP score is clamped below the mate threshold
            score_cp = max(-9999, min(9999, score_cp))

        return EngineEval(
            best_uci=best_uci,
            pv_uci=pv_uci,
            score_cp=score_cp
        )
