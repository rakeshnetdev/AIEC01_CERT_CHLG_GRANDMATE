import logging
import re
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

import chess
from config.settings import get_settings
from coach.schemas.models import Game, MoveAnalysis
from coach.agent.prompts import NARRATOR_SYSTEM_PROMPT
from coach.llm.gateway import chat
from coach.tools.fetch_games import fetch_games
from coach.tools.engine_eval import engine_eval
from coach.rag.pipeline import retrieve_context
from coach.ingestion.pgn import parse_pgn
from coach.agent.memory import get_memory_saver

logger = logging.getLogger(__name__)

class CoachState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    username: Optional[str]
    source: Optional[str]
    pgn: Optional[str]
    game: Optional[Game]
    analyses: List[MoveAnalysis]
    rag_context: str
    output: str
    retriever_type: Optional[str]
    retry_count: Optional[int]
    grounding_log: Optional[List[dict]]


def fetch_and_analyse_node(state: CoachState) -> dict:
    """Ingests or parses the game, then runs the per-move Stockfish centipawn engine analysis."""
    logger.info("Running fetch_and_analyse node")
    game = state.get("game")
    if isinstance(game, dict):
        game = Game(**game)
    pgn = state.get("pgn")
    username = state.get("username")
    source = state.get("source")
    
    if game and state.get("analyses"):
        logger.info("Game and analyses already present in state, skipping analysis.")
        return {}
        
    if not game:
        if pgn:
            game = parse_pgn(pgn, source=source or "upload", username=username or "user")
        elif username and source:
            games = fetch_games(username=username, source=source, max_games=1)
            if not games:
                return {"output": "Failed to fetch games for user."}
            game = Game(**games[0])
            
    if not game:
        return {"output": "No game data provided."}
        
    from coach.analysis.pipeline import analyze_game
    analyses = analyze_game(game, get_settings())
    return {
        "game": game,
        "analyses": analyses
    }


def retrieve_rag_context_node(state: CoachState) -> dict:
    """Retrieves tactical concept notes using the custom RAG pipeline."""
    logger.info("Running retrieve_rag_context node")
    game = state.get("game")
    analyses = state.get("analyses", [])
    retriever_type = state.get("retriever_type") or get_settings().retriever_type
    
    if not analyses:
        return {}
        
    # Query using tactical themes identified
    queries = []
    for ma in analyses:
        if ma.label != "ok" and ma.theme:
            queries.append(ma.theme)
            
    if game and game.opening_name:
        queries.append(game.opening_name)
        
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)
            
    settings = get_settings()
    rag_parts = []
    for q in unique_queries[:3]:
        try:
            results = retrieve_context(q, persist_dir=settings.chroma_db_path, limit=1, retriever_type=retriever_type)
            for r in results:
                rag_parts.append(r["text"])
        except Exception as e:
            logger.error(f"Error querying RAG for '{q}': {e}")
            
    rag_context = "\n\n".join(rag_parts)
    return {"rag_context": rag_context}


def narrator_agent_node(state: CoachState) -> dict:
    """Translates engine evaluations and RAG context into a cohesive Markdown summary."""
    logger.info("Running narrator_agent node")
    game = state.get("game")
    analyses = state.get("analyses", [])
    
    # Exclude OK moves from prompt summary to preserve token budget
    processed_analyses = []
    for ma in analyses:
        if isinstance(ma, dict):
            if ma.get("label") != "ok":
                processed_analyses.append(ma)
        else:
            if ma.label != "ok":
                processed_analyses.append(ma)
    analyses = processed_analyses
    
    rag_context = state.get("rag_context", "")
    
    if not game:
        return {"output": "No game available to narrate."}
        
    # Format move analysis list
    summary_lines = []
    for ma in analyses:
        summary_lines.append(
            f"- Ply {ma.ply} ({ma.played_san} played, best was {ma.best_san}). "
            f"Score before: {ma.eval_before_cp}, after: {ma.eval_after_cp}. "
            f"Loss: {ma.centipawn_loss}. Severity: {ma.label}. Theme: {ma.theme or 'None'}."
        )
    move_analyses_summary = "\n".join(summary_lines)
    
    # Format system prompt
    system_prompt = NARRATOR_SYSTEM_PROMPT.format(
        white_player=game.white,
        black_player=game.black,
        user_color=game.user_color,
        opening_name=game.opening_name or "Unknown Opening",
        result=game.result,
        move_analyses_summary=move_analyses_summary,
        rag_context=rag_context
    )
    
    # Build LLM messages
    llm_messages = [{"role": "system", "content": system_prompt}]
    
    for m in state.get("messages", []):
        if isinstance(m, HumanMessage):
            llm_messages.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            # If it's a grounding feedback message, inject it to guide corrections
            if m.content.startswith("Grounding check: approved=False"):
                llm_messages.append({"role": "system", "content": f"Feedback from evaluator: {m.content}. Please rewrite the summary correcting these issues."})
            else:
                llm_messages.append({"role": "assistant", "content": m.content})
        elif isinstance(m, SystemMessage):
            llm_messages.append({"role": "system", "content": m.content})
            
    if not any(msg["role"] == "user" for msg in llm_messages):
        llm_messages.append({"role": "user", "content": "Please narrate my game."})
        
    # Request completion from LiteLLM gateway
    output = chat(messages=llm_messages)
    
    return {
        "output": output,
        "messages": [AIMessage(content=output)]
    }


def check_deterministic_grounding(output: str, game: Optional[Game], analyses: List[MoveAnalysis]) -> tuple[bool, str]:
    """Scans text output to ensure all mentioned chess moves are legal in the game's context."""
    # Matches patterns like "Nf6", "e4", "1.e4", "Bxh7+", "O-O"
    move_candidates = re.findall(r"\b[KQRBN]?[a-h1-8]?x?[a-h][1-8][+#]?\b|O-O(?:-O)?", output)
    
    valid_moves_in_text = []
    for move_str in move_candidates:
        # Filter out isolated letters that are not moves (e.g. file descriptions)
        if move_str.lower() in ["a", "b", "c", "d", "e", "f", "g", "h"]:
            continue
        valid_moves_in_text.append(move_str)
        
    if not valid_moves_in_text:
        return True, ""
        
    fens = [ma.fen_before for ma in analyses if ma.fen_before]
    if not fens and game:
        fens = ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]
        
    for move_str in valid_moves_in_text:
        legal_somewhere = False
        for fen in fens:
            board = chess.Board(fen)
            try:
                board.parse_san(move_str)
                legal_somewhere = True
                break
            except Exception:
                pass
        if not legal_somewhere:
            return False, f"The move '{move_str}' is illegal in any analyzed position in this game."
            
    return True, ""


def grounding_guard_node(state: CoachState) -> dict:
    """Validates the narrative output using either LLM-as-a-Judge or deterministic rules."""
    logger.info("Running grounding_guard node")
    
    output = state.get("output", "")
    game = state.get("game")
    analyses = state.get("analyses", [])
    retry_count = state.get("retry_count") or 0
    
    # Detect if this is a chat follow-up (prior AI messages exist from initial review)
    existing_ai_messages = [m for m in state.get("messages", []) if isinstance(m, AIMessage) and not m.content.startswith("Grounding check:")]
    is_chat_followup = len(existing_ai_messages) > 1  # More than just the current narrator output
    
    s = get_settings()
    use_llm_judge = getattr(s, "use_llm_judge", True)
    
    # Chat follow-ups always use deterministic check (fast, ~5ms)
    if is_chat_followup and use_llm_judge:
        logger.info("Chat follow-up detected — forcing deterministic grounding (skipping LLM Judge)")
        use_llm_judge = False
    
    is_approved = True
    critique = ""
    
    if use_llm_judge:
        logger.info("Using LLM-as-a-Judge for grounding validation")
        import json
        
        # Format move analysis list for LLM context
        summary_lines = []
        for ma in analyses:
            summary_lines.append(
                f"- Ply {ma.ply} ({ma.played_san} played, best was {ma.best_san}). "
                f"Loss: {ma.centipawn_loss}. Severity: {ma.label}. Theme: {ma.theme or 'None'}."
            )
        move_analyses_summary = "\n".join(summary_lines)
        game_details = f"White: {game.white}, Black: {game.black}, Color: {game.user_color}, Opening: {game.opening_name or 'Unknown'}" if game else "No game info"
        
        judge_prompt = (
            "You are a chess master and certification evaluator. Your job is to judge if the following "
            "chess analysis narrative is conceptually correct and uses valid, legal moves.\n\n"
            f"Game Details:\n{game_details}\n\n"
            f"Engine Analysis details:\n{move_analyses_summary}\n\n"
            f"Narrative Draft:\n{output}\n\n"
            "Does this narrative contain incorrect strategic concepts, rules violations, or suggest illegal moves? "
            "You MUST respond in a strict JSON format with exactly three fields: "
            "'explanation_approved' (boolean, true if no mistakes/errors found, false otherwise), "
            "'error_category' (string, e.g. 'none', 'illegal_move', 'incorrect_motif'), and "
            "'detailed_critique' (string, empty if approved, explanation of the error if false).\n"
            "Do not include any other text outside the JSON."
        )
        
        judge_messages = [{"role": "user", "content": judge_prompt}]
        
        try:
            response_text = chat(messages=judge_messages)
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            is_approved = data.get("explanation_approved", True)
            critique = data.get("detailed_critique", "")
            logger.info(f"LLM Judge response parsed: approved={is_approved}, critique='{critique}'")
        except Exception as e:
            logger.warning(f"LLM Judge query/parsing failed: {e}. Falling back to deterministic check.")
            use_llm_judge = False
            
    if not use_llm_judge:
        logger.info("Using deterministic python-chess guard for validation")
        is_approved, critique = check_deterministic_grounding(output, game, analyses)
        logger.info(f"Deterministic check result: approved={is_approved}, critique='{critique}'")
        
    # Build grounding event record
    mode_used = "llm_judge" if use_llm_judge else "deterministic"
    event = {
        "attempt": retry_count + 1,
        "mode": mode_used,
        "approved": is_approved,
        "error_category": "none" if is_approved else "illegal_move" if not use_llm_judge else data.get("error_category", "unknown") if 'data' in dir() else "unknown",
        "critique": critique,
        "narrative_snippet": output[:200] if output else ""
    }
    
    existing_log = list(state.get("grounding_log") or [])
    existing_log.append(event)
    
    return {
        "retry_count": retry_count + 1,
        "grounding_log": existing_log,
        "messages": [AIMessage(content=f"Grounding check: approved={is_approved}, critique={critique}")] if not is_approved else [],
        "output": output
    }


def should_continue_guard(state: CoachState) -> str:
    """Decides if the graph should proceed to END or route back to narrator_agent for correction."""
    retry_count = state.get("retry_count") or 0
    messages = state.get("messages", [])
    
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].content.startswith("Grounding check: approved=False"):
        if retry_count < 3:
            logger.warning(f"Grounding check failed. Attempt {retry_count}/3. Regenerating narration.")
            return "regenerate"
        else:
            logger.error("Grounding check failed 3 times. Forcing continuation to avoid infinite loops.")
            
    return "continue"


def compile_coach_graph():
    """Compiles the Coach StateGraph workflow with MemorySaver checkpointing."""
    workflow = StateGraph(CoachState)
    
    # Add nodes
    workflow.add_node("fetch_and_analyse", fetch_and_analyse_node)
    workflow.add_node("retrieve_rag_context", retrieve_rag_context_node)
    workflow.add_node("narrator_agent", narrator_agent_node)
    workflow.add_node("grounding_guard", grounding_guard_node)
    
    # Set execution edges
    workflow.set_entry_point("fetch_and_analyse")
    workflow.add_edge("fetch_and_analyse", "retrieve_rag_context")
    workflow.add_edge("retrieve_rag_context", "narrator_agent")
    workflow.add_edge("narrator_agent", "grounding_guard")
    
    # Define conditional routing from grounding_guard
    workflow.add_conditional_edges(
        "grounding_guard",
        should_continue_guard,
        {
            "continue": END,
            "regenerate": "narrator_agent"
        }
    )
    
    checkpointer = get_memory_saver()
    return workflow.compile(checkpointer=checkpointer)
