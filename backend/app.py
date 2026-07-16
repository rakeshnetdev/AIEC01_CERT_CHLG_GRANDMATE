import sys
import os
import time
import logging
from typing import Optional, List, Dict

# Inject backend/ and backend/src/ directories into sys.path to allow imports from any working directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
sys.path.append(os.path.join(backend_dir, "src"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import get_settings
from coach.schemas.models import (
    Game,
    MoveAnalysis,
    Explanation,
    Weakness,
    Drill,
    CoachReport,
    Source,
    DeveloperInsight
)
from coach.agent.graph import compile_coach_graph
from coach.guardrails import validate_request, is_safe_output
from langchain_core.messages import HumanMessage, AIMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Grandmate API", version="0.1.0")

# Enable CORS for the local React/Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev/submission simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compile LangGraph instance at startup
coach_graph = compile_coach_graph()


class ReviewRequest(BaseModel):
    username: Optional[str] = None
    source: Optional[Source] = None
    max_games: int = 1
    pgn: Optional[str] = None
    session_id: Optional[str] = None
    retriever_type: Optional[str] = "hybrid"


class ChatRequest(BaseModel):
    message: str
    session_id: str


# ==========================================
# Clean, Organized Helper Functions
# ==========================================

def _validate_input_request(value: Optional[str]) -> None:
    """Validates input string for command injections or length limits."""
    if value and (" " in value or len(value) > 30):
        validate_request(value)


def _parse_graph_output(final_state: dict) -> tuple[Game, List[MoveAnalysis], str]:
    """Extracts and parses the Chess Game object, its MoveAnalysis list, and the RAG context from the Graph state."""
    game_data = final_state.get("game")
    if isinstance(game_data, dict):
        game = Game(**game_data)
    else:
        game = game_data
        
    if not game:
        raise HTTPException(status_code=404, detail="No chess game found or parsed.")
        
    analyses_raw = final_state.get("analyses", [])
    analyses = []
    for ma in analyses_raw:
        if isinstance(ma, dict):
            analyses.append(MoveAnalysis(**ma))
        else:
            analyses.append(ma)
            
    rag_context = final_state.get("rag_context", "")
    return game, analyses, rag_context


def _build_findings_and_weaknesses(analyses: List[MoveAnalysis]) -> tuple[List[Explanation], List[Weakness]]:
    """Calculates move explanations (findings) and groups mistakes into top weaknesses."""
    findings = []
    weakness_counts = {}
    
    for ma in analyses:
        if ma.label != "ok":
            why = f"Played {ma.played_san}, but best was {ma.best_san} (centipawn loss: {ma.centipawn_loss})."
            correct_plan = f"Plan: {', '.join(ma.pv_san)}" if ma.pv_san else f"Best move was {ma.best_san}."
            findings.append(
                Explanation(
                    ply=ma.ply,
                    label=ma.label,
                    why=why,
                    correct_plan=correct_plan,
                    sources=[],
                    grounded=True
                )
            )
            theme = ma.theme or "Tactics"
            if theme not in weakness_counts:
                weakness_counts[theme] = []
            weakness_counts[theme].append(ma.ply)
            
    top_weaknesses = []
    for theme, plies in weakness_counts.items():
        top_weaknesses.append(
            Weakness(
                theme=theme,
                count=len(plies),
                example_plies=plies
            )
        )
    top_weaknesses.sort(key=lambda w: w.count, reverse=True)
    return findings, top_weaknesses


def _generate_recommended_drills(top_weaknesses: List[Weakness]) -> List[Drill]:
    """Generates Lichess practice drill puzzles corresponding to the top identified weaknesses."""
    drills = []
    for idx, w in enumerate(top_weaknesses, start=1):
        theme = w.theme
        if theme.lower() == "pin":
            url = "https://lichess.org/practice/basic-tactics/the-pin"
        elif theme.lower() == "fork":
            url = "https://lichess.org/practice/basic-tactics/the-fork"
        elif theme.lower() == "check":
            url = "https://lichess.org/practice/training"
        else:
            url = "https://lichess.org/practice"
            
        drills.append(
            Drill(
                puzzle_id=f"{theme.lower()}_drill_{idx}",
                theme=theme,
                rating=1500,
                url=url
            )
        )
    return drills


def _build_position_explanations(analyses: List[MoveAnalysis], game: Game, top_weaknesses: List[Weakness]) -> List[str]:
    """Builds a summary of position explanations for key moments."""
    position_explanation = []
    notable_moves = [ma for ma in analyses if ma.label != "ok"]
    if notable_moves:
        for ma in notable_moves[:3]:
            theme = ma.theme or "the position"
            position_explanation.append(
                f"At ply {ma.ply}, {ma.played_san} was a {ma.label}; the stronger choice was {ma.best_san}, which improves {theme}."
            )
            
    if not position_explanation:
        opening_hint = game.opening_name or "your opening"
        position_explanation = [
            f"In {opening_hint}, keep the center under control and develop your pieces with purpose.",
            "Your review suggests you should look for simple, stable moves before taking tactical risks.",
            "A practical next step is to compare the key moments with the engine line and reinforce the pattern."
        ]
        
    if top_weaknesses:
        first_theme = top_weaknesses[0].theme
        if not any(first_theme.lower() in item.lower() for item in position_explanation):
            position_explanation.insert(1, f"The recurring theme in your game was {first_theme.lower()}, so review that pattern closely.")
            
    while len(position_explanation) < 3:
        position_explanation.append(
            "Keep building the position patiently and look for the next best practical move."
        )
    return position_explanation[:5]


def _build_system_prompt(game: Game, analyses: List[MoveAnalysis], rag_context: str) -> str:
    """Formats the narrator prompt template with active chess game details and move lists."""
    from coach.agent.prompts import NARRATOR_SYSTEM_PROMPT
    
    summary_lines = []
    for ma in analyses:
        ma_dict = ma if isinstance(ma, dict) else ma.model_dump()
        summary_lines.append(
            f"- Ply {ma_dict.get('ply')} ({ma_dict.get('played_san')} played, best was {ma_dict.get('best_san')}). "
            f"Loss: {ma_dict.get('centipawn_loss')}. Severity: {ma_dict.get('label')}. Theme: {ma_dict.get('theme') or 'None'}."
        )
    move_analyses_summary = "\n".join(summary_lines)
    
    white_player = "White"
    black_player = "Black"
    user_color = "white"
    opening_name = "Unknown Opening"
    result = "*"
    if game:
        game_dict = game if isinstance(game, dict) else game.model_dump()
        white_player = game_dict.get("white", "White")
        black_player = game_dict.get("black", "Black")
        user_color = game_dict.get("user_color", "white")
        opening_name = game_dict.get("opening_name") or "Unknown Opening"
        result = game_dict.get("result", "*")

    return NARRATOR_SYSTEM_PROMPT.format(
        white_player=white_player,
        black_player=black_player,
        user_color=user_color,
        opening_name=opening_name,
        result=result,
        move_analyses_summary=move_analyses_summary,
        rag_context=rag_context
    )


# ==========================================
# Route Handlers
# ==========================================

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/review", response_model=CoachReport)
def review_game(request: ReviewRequest):
    logger.info(f"POST /review called for user={request.username}, source={request.source}")
    
    # 1. Guardrail input validation
    try:
        _validate_input_request(request.username)
        if request.pgn:
            validate_request(request.pgn)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    start_time = time.time()
    
    # 2. Invoke LangGraph Orchestrator
    inputs = {
        "messages": [],
        "username": request.username,
        "source": request.source,
        "pgn": request.pgn,
        "game": None,
        "analyses": [],
        "rag_context": "",
        "output": "",
        "retriever_type": request.retriever_type
    }
    
    thread_id = request.session_id or f"review_{request.username or 'anonymous'}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        final_state = coach_graph.invoke(inputs, config=config)
    except Exception as e:
        logger.error(f"Error running coach agent graph: {e}")
        raise HTTPException(status_code=500, detail=f"Coach agent execution failed: {e}")
        
    # 3. Parse state outputs
    game, analyses, rag_context = _parse_graph_output(final_state)
    summary = final_state.get("output", "")
    
    # 4. Guardrail output safety check
    if not is_safe_output(summary):
        summary = "[Moderated Response] The generated review contained content that was flagged as unsafe. Please focus on standard chess strategies."
        
    # 5. Process tactical findings & weaknesses
    findings, top_weaknesses = _build_findings_and_weaknesses(analyses)
    
    # 6. Generate drill recommendations
    drills = _generate_recommended_drills(top_weaknesses)
    
    # 7. Formulate position explanations
    position_explanation = _build_position_explanations(analyses, game, top_weaknesses)
    
    # 8. Reconstruct developer insights metadata
    rag_queries = [game.opening_name] if game.opening_name else []
    for ma in analyses:
        if ma.label != "ok" and ma.theme:
            if ma.theme.lower() not in ["tactics", "opening", "endgame", "check"]:
                rag_queries.append(ma.theme)
            
    system_prompt = _build_system_prompt(game, analyses, rag_context)
    dev_insight = DeveloperInsight(
        graph_state="finished",
        active_nodes=["fetch_and_analyse", "retrieve_rag_context", "narrator_agent"],
        rag_queries=rag_queries,
        rag_context=rag_context,
        raw_prompt=system_prompt,
        stockfish_raw=analyses,
        retriever_type=request.retriever_type or "hybrid"
    )
    
    return CoachReport(
        username=request.username or game.white,
        games_reviewed=1,
        summary=summary,
        findings=findings,
        top_weaknesses=top_weaknesses,
        drills=drills,
        position_explanation=position_explanation,
        latency_s=round(time.time() - start_time, 2),
        cost_usd=0.002,  # Estimated trace cost
        developer_insight=dev_insight
    )


@app.post("/chat")
def chat_message(request: ChatRequest):
    logger.info(f"POST /chat called for session_id={request.session_id}")
    
    # 1. Guardrail input validation
    try:
        validate_request(request.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # 2. Check checkpointer session state
    config = {"configurable": {"thread_id": request.session_id}}
    current_state = coach_graph.get_state(config)
    if not current_state or not current_state.values or not current_state.values.get("game"):
        logger.warning(f"Chat request failed: No game loaded in session {request.session_id}")
        return {
            "reply": "Please load and analyze a chess game first before asking coaching questions!",
            "developer_insight": None
        }
        
    # 3. Invoke LangGraph with conversational message
    inputs = {
        "messages": [HumanMessage(content=request.message)]
    }
    try:
        final_state = coach_graph.invoke(inputs, config=config)
    except Exception as e:
        logger.error(f"Error running chat conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Chat execution failed: {e}")
        
    # 4. Extract reply content
    messages = final_state.get("messages", [])
    reply = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            reply = m.content
            break
            
    if not reply:
        reply = "I'm sorry, I could not generate a response."
        
    # 5. Guardrail output safety check
    if not is_safe_output(reply):
        reply = "I cannot continue this specific conversation topic. Let's focus on chess strategies and analysis."
        
    # 6. Parse game context & structure insights
    game, analyses, rag_context = _parse_graph_output(final_state)
    system_prompt = _build_system_prompt(game, analyses, rag_context)
    
    # Format message history as raw prompt context
    history_str = []
    for m in messages:
        sender = "User" if isinstance(m, HumanMessage) else "Assistant"
        history_str.append(f"{sender}: {m.content}")
    raw_prompt = f"--- System Prompt ---\n{system_prompt}\n\n--- Conversation History ---\n" + "\n".join(history_str)
    
    rag_queries = [game.opening_name] if game.opening_name else []
    for ma in analyses:
        if ma.label != "ok" and ma.theme:
            if ma.theme.lower() not in ["tactics", "opening", "endgame", "check"]:
                rag_queries.append(ma.theme)
            
    dev_insight = DeveloperInsight(
        graph_state="finished (chat follow-up)",
        active_nodes=["narrator_agent"],
        rag_queries=rag_queries,
        rag_context=rag_context,
        raw_prompt=raw_prompt,
        stockfish_raw=analyses,
        retriever_type=current_state.values.get("retriever_type") or "hybrid"
    )
    
    return {
        "reply": reply,
        "developer_insight": dev_insight
    }


@app.get("/carlsen-games")
def get_carlsen_games():
    """Reads the first 6 games from Carlsen.pgn and returns their metadata and raw PGN text."""
    pgn_path = "/Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/prj/grandmate/backend/data/corpus/Carlsen.pgn"
    if not os.path.exists(pgn_path):
        pgn_path = "data/corpus/Carlsen.pgn"
        
    if not os.path.exists(pgn_path):
        logger.warning(f"Carlsen PGN file not found at {pgn_path}")
        return []
        
    games = []
    import chess.pgn
    try:
        with open(pgn_path, "r", encoding="utf-8") as f:
            for _ in range(6):
                game = chess.pgn.read_game(f)
                if not game:
                    break
                    
                exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
                pgn_str = game.accept(exporter)
                
                white = game.headers.get("White", "Unknown")
                black = game.headers.get("Black", "Unknown")
                result = game.headers.get("Result", "*")
                date = game.headers.get("Date", "Unknown")
                
                games.append({
                    "label": f"{white} vs {black} ({date}) - {result}",
                    "pgn": pgn_str
                })
    except Exception as e:
        logger.error(f"Error reading Carlsen.pgn: {e}")
        return []
            
    return games
