import logging
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

import chess
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
                raise ValueError(f"No games found for user {username} on {source}")
            game = games[0]
            if isinstance(game, dict):
                game = Game(**game)
        else:
            raise ValueError("No game, PGN, or username/source provided for analysis.")
            
    # Run analysis pipeline
    from coach.analysis.pipeline import analyze_game
    from config.settings import get_settings
    settings = get_settings()
    analyses = analyze_game(game, settings)
    
    return {
        "game": game,
        "analyses": analyses
    }


def retrieve_rag_context_node(state: CoachState) -> dict:
    """Collects tactical and opening terms from the analyses, querying ChromaDB for context."""
    logger.info("Running retrieve_rag_context node")
    if state.get("rag_context"):
        logger.info("RAG context already present in state, skipping retrieval.")
        return {}
        
    game = state.get("game")
    if isinstance(game, dict):
        game = Game(**game)
        
    analyses = state.get("analyses", [])
    processed_analyses = []
    for ma in analyses:
        if isinstance(ma, dict):
            processed_analyses.append(MoveAnalysis(**ma))
        else:
            processed_analyses.append(ma)
    analyses = processed_analyses
    
    if not game:
        return {"rag_context": ""}
        
    queries = []
    if game.opening_name:
        queries.append(game.opening_name)
        
    for ma in analyses:
        if ma.label != "ok" and ma.theme:
            if ma.theme.lower() not in ["tactics", "opening", "endgame", "check"]:
                queries.append(ma.theme)
            
    # De-duplicate queries
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)
            
    from config.settings import get_settings
    settings = get_settings()
    
    # Retrieve active retriever type from state or default settings
    r_type = state.get("retriever_type") or settings.retriever_type
    
    rag_parts = []
    # Query ChromaDB for top matched concepts (limit to top 3 queries)
    for q in unique_queries[:3]:
        try:
            results = retrieve_context(q, persist_dir=settings.chroma_db_path, limit=1, retriever_type=r_type)
            for r in results:
                rag_parts.append(r["text"])
        except Exception as e:
            logger.error(f"Error querying RAG for '{q}': {e}")
            
    rag_context = "\n\n".join(rag_parts)
    return {
        "rag_context": rag_context
    }


def narrator_agent_node(state: CoachState) -> dict:
    """Formats the narrator prompt, passes it to the LiteLLM gateway, and saves the narration."""
    logger.info("Running narrator_agent node")
    game = state.get("game")
    if isinstance(game, dict):
        game = Game(**game)
        
    analyses = state.get("analyses", [])
    processed_analyses = []
    for ma in analyses:
        if isinstance(ma, dict):
            processed_analyses.append(MoveAnalysis(**ma))
        else:
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


def compile_coach_graph():
    """Compiles the Coach StateGraph workflow with MemorySaver checkpointing."""
    workflow = StateGraph(CoachState)
    
    # Add nodes
    workflow.add_node("fetch_and_analyse", fetch_and_analyse_node)
    workflow.add_node("retrieve_rag_context", retrieve_rag_context_node)
    workflow.add_node("narrator_agent", narrator_agent_node)
    
    # Set execution edges
    workflow.set_entry_point("fetch_and_analyse")
    workflow.add_edge("fetch_and_analyse", "retrieve_rag_context")
    workflow.add_edge("retrieve_rag_context", "narrator_agent")
    workflow.add_edge("narrator_agent", END)
    
    checkpointer = get_memory_saver()
    return workflow.compile(checkpointer=checkpointer)
