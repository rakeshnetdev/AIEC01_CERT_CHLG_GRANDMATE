import logging
import re
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

import chess
from config.settings import get_settings
from coach.schemas.models import Game, MoveAnalysis
from coach.agent.prompts import (
    NARRATOR_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    STRATEGY_SYSTEM_PROMPT,
    RULES_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT
)
from coach.llm.gateway import chat
from coach.tools.fetch_games import fetch_games
from coach.tools.engine_eval import engine_eval
from coach.rag.pipeline import retrieve_context
from coach.ingestion.pgn import parse_pgn
from coach.agent.memory import get_memory_saver

logger = logging.getLogger(__name__)

def append_logs(left: Optional[List[str]], right: Optional[List[str]]) -> List[str]:
    res = []
    if left:
        res.extend(left)
    if right:
        res.extend(right)
    return res

def append_agent_steps(left: Optional[List[dict]], right: Optional[List[dict]]) -> List[dict]:
    res = []
    if left:
        res.extend(left)
    if right:
        res.extend(right)
    return res

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
    delegated_specialist: Optional[str]
    strategy_findings: Optional[dict]
    rules_findings: Optional[dict]
    execution_logs: Annotated[List[str], append_logs]
    agent_steps: Annotated[List[dict], append_agent_steps]



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
        return {
            "execution_logs": ["fetch_and_analyse: Game and analyses already loaded in state, skipping analysis."],
            "agent_steps": [{
                "agent_name": "PGN Ingestion & Stockfish Analysis",
                "prompt": "(Skipped — game and analyses already present in state)",
                "response": "Reused existing game and move analyses from state."
            }]
        }

    if not game:
        if pgn:
            game = parse_pgn(pgn, source=source or "upload", username=username or "user")
        elif username and source:
            games = fetch_games(username=username, source=source, max_games=1)
            if not games:
                return {
                    "output": "Failed to fetch games for user.",
                    "execution_logs": ["fetch_and_analyse: Failed to fetch games for user."],
                    "agent_steps": [{
                        "agent_name": "PGN Ingestion & Stockfish Analysis",
                        "prompt": f"fetch_games(username='{username}', source='{source}', max_games=1)",
                        "response": "Failed — no games returned for this user/source."
                    }]
                }
            game = Game(**games[0])

    if not game:
        return {
            "output": "No game data provided.",
            "execution_logs": ["fetch_and_analyse: Failed - no game data provided."],
            "agent_steps": [{
                "agent_name": "PGN Ingestion & Stockfish Analysis",
                "prompt": "(No PGN, username, or source provided in request)",
                "response": "Failed — no game data provided."
            }]
        }

    from coach.analysis.pipeline import analyze_game
    analyses = analyze_game(game, get_settings())
    prompt_desc = (
        f"parse_pgn(source='{source or 'upload'}', username='{username or 'user'}')" if pgn
        else f"fetch_games(username='{username}', source='{source}', max_games=1)"
    )
    return {
        "game": game,
        "analyses": analyses,
        "execution_logs": [f"fetch_and_analyse: Successfully parsed and analyzed game with Stockfish. Found {len(analyses)} move analyses."],
        "agent_steps": [{
            "agent_name": "PGN Ingestion & Stockfish Analysis",
            "prompt": prompt_desc,
            "response": f"Parsed game ({game.white} vs {game.black}, {game.result}). Ran Stockfish centipawn analysis on {len(analyses)} moves."
        }]
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
    return {
        "rag_context": rag_context,
        "execution_logs": [f"retrieve_rag_context: Pre-retrieved general game concepts. Queries: {unique_queries[:3]}. Retrieved {len(rag_parts)} RAG blocks."]
    }


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
    
    # Render prompt text for DevInsights tracing
    prompt_str = "\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in llm_messages])
    
    return {
        "output": output,
        "messages": [AIMessage(content=output)],
        "agent_steps": [{
            "agent_name": "Narrator Agent",
            "prompt": prompt_str,
            "response": output
        }]
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
    
    node_out = {
        "retry_count": retry_count + 1,
        "grounding_log": existing_log,
        "messages": [AIMessage(content=f"Grounding check: approved={is_approved}, critique={critique}")] if not is_approved else [],
        "output": output,
        "execution_logs": [f"grounding_guard: Evaluated response using '{mode_used}' mode. Approved: {is_approved}. Critique: '{critique or 'None'}'."]
    }
    
    if mode_used == "llm_judge":
        node_out["agent_steps"] = [{
            "agent_name": f"Grounding Judge (Attempt {retry_count + 1})",
            "prompt": f"[USER]: {judge_prompt}",
            "response": response_text
        }]
    else:
        node_out["agent_steps"] = [{
            "agent_name": f"Grounding Judge (Attempt {retry_count + 1})",
            "prompt": f"Deterministic chess legal move check. Text scanned: {output[:300]}...",
            "response": f"Approved: {is_approved}. Critique: {critique or 'None'}"
        }]
        
    return node_out


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


def router_agent_node(state: CoachState) -> dict:
    """Coordinates and classifies the user intent to delegate to specialists."""
    logger.info("Running router_agent node")
    messages = state.get("messages", [])
    
    if not messages:
        return {
            "delegated_specialist": None,
            "execution_logs": ["router_agent: No messages present, skipping routing."],
            "agent_steps": [{
                "agent_name": "Router Agent",
                "prompt": "(Skipped — no messages present)",
                "response": "None (nothing to route)"
            }]
        }

    has_strategy = state.get("strategy_findings") is not None
    has_rules = state.get("rules_findings") is not None

    # Both findings gathered — route to synthesizer
    if has_strategy and has_rules:
        logger.info("Both strategy and rules findings present. Routing to synthesizer.")
        return {
            "delegated_specialist": None,
            "execution_logs": ["router_agent: Both findings gathered. Routing to synthesizer."],
            "agent_steps": [{
                "agent_name": "Router Agent",
                "prompt": "(Fast-path — strategy and rules findings both gathered)",
                "response": "synthesizer (both-gathered fast-path)"
            }]
        }
    
    # Only strategy done — route to rules next (no LLM call needed)
    if has_strategy and not has_rules:
        logger.info("Strategy findings present, routing to rules specialist.")
        return {
            "delegated_specialist": "rules",
            "execution_logs": ["router_agent: Strategy done. Fast-routing to rules specialist."],
            "agent_steps": [{
                "agent_name": "Router Agent",
                "prompt": "(Fast-path — strategy already gathered, routing to rules)",
                "response": "rules (sequential fast-path)"
            }]
        }
    
    # Only rules done — route to strategy next (no LLM call needed)  
    if has_rules and not has_strategy:
        logger.info("Rules findings present, routing to strategy specialist.")
        return {
            "delegated_specialist": "strategy",
            "execution_logs": ["router_agent: Rules done. Fast-routing to strategy specialist."],
            "agent_steps": [{
                "agent_name": "Router Agent",
                "prompt": "(Fast-path — rules already gathered, routing to strategy)",
                "response": "strategy (sequential fast-path)"
            }]
        }
    
    # Fast-path: initial review flow has no HumanMessage — skip LLM call and default to strategy
    has_human_message = any(isinstance(m, HumanMessage) for m in messages)
    if not has_human_message:
        logger.info("No user message detected (initial review). Defaulting to strategy specialist.")
        return {
            "delegated_specialist": "strategy",
            "execution_logs": ["router_agent: Initial review flow — skipping LLM, defaulting to strategy specialist."],
            "agent_steps": [{
                "agent_name": "Router Agent",
                "prompt": "(Skipped — no user message in initial review)",
                "response": "strategy (fast-path default)"
            }]
        }
        
    # Build prompt context
    llm_messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]
    for m in messages:
        if isinstance(m, HumanMessage):
            llm_messages.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            if not m.content.startswith("Grounding check:"):
                llm_messages.append({"role": "assistant", "content": m.content})
                
    # Render prompt text for DevInsights tracing
    prompt_str = "\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in llm_messages])
    
    try:
        response = chat(messages=llm_messages)
        choice = response.strip().lower()
        if "strategy" in choice:
            delegated = "strategy"
        elif "rules" in choice:
            delegated = "rules"
        else:
            delegated = None
    except Exception as e:
        logger.error(f"Router Agent LLM error: {e}")
        delegated = None
        response = f"Failed with error: {e}"
        
    logger.info(f"Router Agent selected specialist: {delegated}")
    return {
        "delegated_specialist": delegated,
        "execution_logs": [f"router_agent: Classified intent. Selected specialist: '{delegated}'."],
        "agent_steps": [{
            "agent_name": "Router Agent",
            "prompt": prompt_str,
            "response": response
        }]
    }



def strategy_node(state: CoachState) -> dict:
    """Queries RAG strategies database and calls strategy specialist agent."""
    logger.info("Running strategy node")
    query = state["messages"][-1].content if state.get("messages") else "tactical themes"
    settings = get_settings()
    
    # Retrieve strategies context
    docs = retrieve_context(query, persist_dir=settings.chroma_db_path, limit=2, bucket="strategies")
    rag_context = "\n\n".join([doc["text"] for doc in docs])
    
    # Update rag_context in state for history and compatibility
    existing_rag = state.get("rag_context", "")
    new_rag = existing_rag + ("\n\n" if existing_rag else "") + rag_context
    
    analyses = state.get("analyses", [])
    summary_lines = []
    for ma in analyses:
        if ma.label != "ok":
            summary_lines.append(
                f"- Ply {ma.ply} ({ma.played_san} played, best was {ma.best_san}). Loss: {ma.centipawn_loss}. Theme: {ma.theme or 'None'}."
            )
    move_analyses_summary = "\n".join(summary_lines)
    
    system_prompt = STRATEGY_SYSTEM_PROMPT.format(
        rag_context=rag_context,
        move_analyses_summary=move_analyses_summary
    )
    
    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
    
    try:
        findings_text = chat(messages=llm_messages)
    except Exception as e:
        logger.error(f"Strategy Agent LLM error: {e}")
        findings_text = "Failed to retrieve strategy advice."
        
    findings = {
        "summary": findings_text,
        "source_documents": [doc.get("metadata", {}).get("source", "unknown") for doc in docs],
        "citations": [doc.get("metadata", {}).get("title", doc.get("metadata", {}).get("source", "unknown")) for doc in docs]
    }
    # Render prompt text for DevInsights tracing
    prompt_str = "\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in llm_messages])
    
    return {
        "strategy_findings": findings,
        "rag_context": new_rag,
        "delegated_specialist": None,
        "execution_logs": [f"strategy_node: Retrieved {len(docs)} strategy documents from ChromaDB. Formulated strategy findings using the specialized agent prompt."],
        "agent_steps": [{
            "agent_name": "Strategy Specialist Agent",
            "prompt": prompt_str,
            "response": findings_text
        }]
    }


def rules_node(state: CoachState) -> dict:
    """Queries RAG rules database and calls rules specialist agent."""
    logger.info("Running rules node")
    query = state["messages"][-1].content if state.get("messages") else "laws of chess"
    settings = get_settings()
    
    # Retrieve rules context
    docs = retrieve_context(query, persist_dir=settings.chroma_db_path, limit=2, bucket="rules")
    rag_context = "\n\n".join([doc["text"] for doc in docs])
    
    # Update rag_context in state for history and compatibility
    existing_rag = state.get("rag_context", "")
    new_rag = existing_rag + ("\n\n" if existing_rag else "") + rag_context
    
    system_prompt = RULES_SYSTEM_PROMPT.format(
        rag_context=rag_context
    )
    
    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
    
    try:
        findings_text = chat(messages=llm_messages)
    except Exception as e:
        logger.error(f"Rules Agent LLM error: {e}")
        findings_text = "Failed to retrieve chess rules advice."
        
    findings = {
        "summary": findings_text,
        "source_documents": [doc.get("metadata", {}).get("source", "unknown") for doc in docs],
        "citations": [doc.get("metadata", {}).get("title", doc.get("metadata", {}).get("source", "unknown")) for doc in docs]
    }
    # Render prompt text for DevInsights tracing
    prompt_str = "\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in llm_messages])
    
    return {
        "rules_findings": findings,
        "rag_context": new_rag,
        "delegated_specialist": None,
        "execution_logs": [f"rules_node: Retrieved {len(docs)} rules documents from FIDE rulebook. Formulated rules findings using the rules specialist agent."],
        "agent_steps": [{
            "agent_name": "Rules Specialist Agent",
            "prompt": prompt_str,
            "response": findings_text
        }]
    }


def synthesizer_node(state: CoachState) -> dict:
    """Fuses all available findings and generates final coaching answer."""
    logger.info("Running synthesizer node")
    strategy = state.get("strategy_findings")
    rules = state.get("rules_findings")
    
    strategy_summary = strategy["summary"] if strategy else "No strategic themes analyzed."
    rules_summary = rules["summary"] if rules else "No rules themes analyzed."
    
    system_prompt = SYNTHESIZER_SYSTEM_PROMPT.format(
        strategy_findings=strategy_summary,
        rules_findings=rules_summary
    )
    
    llm_messages = [{"role": "system", "content": system_prompt}]
    for m in state.get("messages", []):
        if isinstance(m, HumanMessage):
            llm_messages.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            if m.content.startswith("Grounding check: approved=False"):
                llm_messages.append({"role": "system", "content": f"Feedback from evaluator: {m.content}. Please rewrite the response correcting these issues."})
            elif not m.content.startswith("Grounding check:"):
                llm_messages.append({"role": "assistant", "content": m.content})
                
    if not any(msg["role"] == "user" for msg in llm_messages):
        llm_messages.append({"role": "user", "content": "Please synthesize the response."})
        
    try:
        output = chat(messages=llm_messages)
    except Exception as e:
        logger.error(f"Synthesizer LLM error: {e}")
        output = "Failed to synthesize response."
        
    # Render prompt text for DevInsights tracing
    prompt_str = "\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in llm_messages])
    
    return {
        "output": output,
        "messages": [AIMessage(content=output)],
        "strategy_findings": None,
        "rules_findings": None,
        "execution_logs": ["synthesizer_node: Fused strategy and rules findings into final Markdown coaching overview."],
        "agent_steps": [{
            "agent_name": "Synthesizer Agent",
            "prompt": prompt_str,
            "response": output
        }]
    }


def should_delegate(state: CoachState) -> str:
    """Routes to the designated specialist node or to synthesis."""
    specialist = state.get("delegated_specialist")
    if specialist == "strategy":
        return "strategy_node"
    elif specialist == "rules":
        return "rules_node"
    else:
        return "synthesizer_node"


def compile_coach_graph():
    """Compiles the rewired multi-agent Coach StateGraph workflow with MemorySaver."""
    workflow = StateGraph(CoachState)
    
    # Add nodes
    workflow.add_node("fetch_and_analyse", fetch_and_analyse_node)
    workflow.add_node("retrieve_rag_context", retrieve_rag_context_node)
    workflow.add_node("router_agent", router_agent_node)
    workflow.add_node("strategy_node", strategy_node)
    workflow.add_node("rules_node", rules_node)
    workflow.add_node("synthesizer_node", synthesizer_node)
    workflow.add_node("grounding_guard", grounding_guard_node)
    
    # Set execution edges
    workflow.set_entry_point("fetch_and_analyse")
    workflow.add_edge("fetch_and_analyse", "retrieve_rag_context")
    workflow.add_edge("retrieve_rag_context", "router_agent")
    
    # Router conditional edges
    workflow.add_conditional_edges(
        "router_agent",
        should_delegate,
        {
            "strategy_node": "strategy_node",
            "rules_node": "rules_node",
            "synthesizer_node": "synthesizer_node"
        }
    )
    
    # Loop back to router after specialists run to allow sequential execution
    workflow.add_edge("strategy_node", "router_agent")
    workflow.add_edge("rules_node", "router_agent")
    
    # Synthesizer runs to grounding guard
    workflow.add_edge("synthesizer_node", "grounding_guard")
    
    # Grounding guard conditional loop back
    workflow.add_conditional_edges(
        "grounding_guard",
        should_continue_guard,
        {
            "continue": END,
            "regenerate": "synthesizer_node"
        }
    )
    
    checkpointer = get_memory_saver()
    return workflow.compile(checkpointer=checkpointer)
