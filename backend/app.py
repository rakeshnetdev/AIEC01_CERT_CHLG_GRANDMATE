import sys
import os
# Inject backend/ and backend/src/ directories into sys.path to allow imports from any working directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
sys.path.append(os.path.join(backend_dir, "src"))

import time
import logging
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config.settings import get_settings
from coach.schemas.models import Game, MoveAnalysis, Explanation, Weakness, Drill, CoachReport, Severity, Source
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

class ChatRequest(BaseModel):
    message: str
    session_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/review", response_model=CoachReport)
def review_game(request: ReviewRequest):
    logger.info(f"POST /review called for user={request.username}, source={request.source}")
    
    # 1. Guardrail input validation
    try:
        if request.username and (" " in request.username or len(request.username) > 30):
            validate_request(request.username)
        if request.pgn:
            validate_request(request.pgn)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    start_time = time.time()
    
    # 2. Invoke LangGraph
    inputs = {
        "messages": [],
        "username": request.username,
        "source": request.source,
        "pgn": request.pgn,
        "game": None,
        "analyses": [],
        "rag_context": "",
        "output": ""
    }
    
    config = {"configurable": {"thread_id": f"review_{request.username or 'anonymous'}"}}
    try:
        final_state = coach_graph.invoke(inputs, config=config)
    except Exception as e:
        logger.error(f"Error running coach agent graph: {e}")
        raise HTTPException(status_code=500, detail=f"Coach agent execution failed: {e}")
        
    game = final_state.get("game")
    analyses = final_state.get("analyses", [])
    summary = final_state.get("output", "")
    
    if not game:
        raise HTTPException(status_code=404, detail="No chess game found or parsed.")
        
    # 3. Guardrail output safety check
    if not is_safe_output(summary):
        summary = "[Moderated Response] The generated review contained content that was flagged as unsafe. Please focus on standard chess strategies."
        
    # 4. Map analyses to Explanation model
    findings: List[Explanation] = []
    weakness_counts: Dict[str, List[int]] = {}
    
    for ma in analyses:
        if ma.label != "ok":
            # Add explanation
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
            # Track weaknesses
            theme = ma.theme or "Tactics"
            if theme not in weakness_counts:
                weakness_counts[theme] = []
            weakness_counts[theme].append(ma.ply)
            
    # 5. Build Weakness list sorted by count descending
    top_weaknesses: List[Weakness] = []
    for theme, plies in weakness_counts.items():
        top_weaknesses.append(
            Weakness(
                theme=theme,
                count=len(plies),
                example_plies=plies
            )
        )
    top_weaknesses.sort(key=lambda w: w.count, reverse=True)
    
    # 6. Map unique weaknesses to drills
    drills: List[Drill] = []
    drill_index = 1
    for w in top_weaknesses:
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
                puzzle_id=f"{theme.lower()}_drill_{drill_index}",
                theme=theme,
                rating=1500,
                url=url
            )
        )
        drill_index += 1
        
    latency = time.time() - start_time
    
    # Estimate token cost (mock)
    cost = 0.002
    
    return CoachReport(
        username=request.username or game.white,
        games_reviewed=1,
        summary=summary,
        findings=findings,
        top_weaknesses=top_weaknesses,
        drills=drills,
        latency_s=round(latency, 2),
        cost_usd=cost
    )


@app.post("/chat")
def chat_message(request: ChatRequest):
    logger.info(f"POST /chat called for session_id={request.session_id}")
    
    # 1. Guardrail input validation
    try:
        validate_request(request.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # 2. Invoke LangGraph with message and session_id config
    config = {"configurable": {"thread_id": request.session_id}}
    inputs = {
        "messages": [HumanMessage(content=request.message)]
    }
    
    try:
        final_state = coach_graph.invoke(inputs, config=config)
    except Exception as e:
        logger.error(f"Error running chat conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Chat execution failed: {e}")
        
    # Get last AI message reply
    messages = final_state.get("messages", [])
    reply = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            reply = m.content
            break
            
    if not reply:
        reply = "I'm sorry, I could not generate a response."
        
    # 3. Guardrail output safety check
    if not is_safe_output(reply):
        reply = "I cannot continue this specific conversation topic. Let's focus on chess strategies and analysis."
        
    return {"reply": reply}
