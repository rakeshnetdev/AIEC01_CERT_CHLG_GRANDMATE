from pydantic import BaseModel
from typing import Literal, Optional, List

Severity = Literal["ok", "inaccuracy", "mistake", "blunder"]
Source = Literal["lichess", "chesscom", "upload"]

class Game(BaseModel):
    game_id: str
    source: Source
    pgn: str
    white: str
    black: str
    white_rating: Optional[int] = None
    black_rating: Optional[int] = None
    result: str
    time_control: Optional[str] = None
    user_color: Literal["white", "black"]
    opening_name: Optional[str] = None

class EngineEval(BaseModel):
    best_uci: str
    pv_uci: List[str]
    score_cp: int   # side-to-move POV, mate clamped ±10000

class MoveAnalysis(BaseModel):
    ply: int
    fen_before: str
    played_uci: str
    played_san: str
    best_uci: str
    best_san: str
    eval_before_cp: int
    eval_after_cp: int
    centipawn_loss: int
    label: Severity
    theme: Optional[str] = None
    pv_san: List[str] = []

class Chunk(BaseModel):
    id: str
    text: str
    source: str
    theme: Optional[str] = None

class Explanation(BaseModel):
    ply: int
    label: Severity
    why: str
    correct_plan: str
    sources: List[str] = []
    grounded: bool = False

class Weakness(BaseModel):
    theme: str
    count: int
    example_plies: List[int]

class Drill(BaseModel):
    puzzle_id: str
    theme: str
    rating: int
    url: str

class DeveloperInsight(BaseModel):
    graph_state: str = "finished"
    active_nodes: List[str] = []
    rag_queries: List[str] = []
    rag_context: str = ""
    raw_prompt: str = ""
    stockfish_raw: List[MoveAnalysis] = []

class CoachReport(BaseModel):
    username: str
    games_reviewed: int
    summary: str
    findings: List[Explanation]
    top_weaknesses: List[Weakness]
    drills: List[Drill]
    position_explanation: List[str] = []
    latency_s: float = 0.0
    cost_usd: float = 0.0
    developer_insight: Optional[DeveloperInsight] = None
