import logging
import re
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

import chess
from config.settings import get_settings
from coach.schemas.models import Game, MoveAnalysis
from coach.agent.prompts import (
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

def merge_rag_context(left: Optional[str], right: Optional[str]) -> str:
    """Concatenates retrieved context. Needs to be a reducer, not a plain overwrite, because
    strategy_node and rules_node can run in the same superstep (the "both" fan-out) and would
    otherwise raise InvalidUpdateError for writing one key twice in a single step."""
    parts = [p for p in (left, right) if p]
    return "\n\n".join(parts)


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
    rag_context: Annotated[str, merge_rag_context]
    output: str
    retriever_type: Optional[str]
    retry_count: Optional[int]
    grounding_log: Optional[List[dict]]
    # Written once per turn by router_agent_node and read immediately by its conditional edge.
    # Not a persistent tracking field: the router is now entered exactly once per invocation.
    dispatch_targets: List[str]
    strategy_findings: Optional[dict]
    rules_findings: Optional[dict]
    execution_logs: Annotated[List[str], append_logs]
    agent_steps: Annotated[List[dict], append_agent_steps]



def _build_move_analyses_summary(analyses: List[MoveAnalysis], max_good: int = 3, max_mistakes: int = 10) -> str:
    """Summarizes both strong moves and mistakes, so the LLM has concrete material for 'what went
    well' as well as 'what went wrong' — a plain mistakes-only list can't produce the former."""
    good_moves = []
    mistakes = []
    for ma in analyses:
        if ma.label != "ok":
            mistakes.append(
                f"- Ply {ma.ply}: {ma.played_san} played ({ma.label}), best was {ma.best_san}. "
                f"Centipawn loss: {ma.centipawn_loss}. Theme: {ma.theme or 'None'}."
            )
        elif ma.played_uci == ma.best_uci:
            good_moves.append(f"- Ply {ma.ply}: {ma.played_san} matched the engine's top choice.")

    lines = []
    if good_moves:
        lines.append("Strong moves (matched the engine's best choice):")
        lines.extend(good_moves[:max_good])
    if mistakes:
        lines.append("Mistakes:")
        lines.extend(mistakes[:max_mistakes])
    return "\n".join(lines) if lines else "No notable moves flagged by the engine for this game."


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
    """Decides if the graph should proceed to END or route back to synthesizer_node for correction."""
    retry_count = state.get("retry_count") or 0
    messages = state.get("messages", [])
    
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].content.startswith("Grounding check: approved=False"):
        if retry_count < 3:
            logger.warning(f"Grounding check failed. Attempt {retry_count}/3. Regenerating narration.")
            return "regenerate"
        else:
            logger.error("Grounding check failed 3 times. Forcing continuation to avoid infinite loops.")
            
    return "continue"


# Small talk the coach can answer without an LLM call. Matching is deliberately
# whole-message (see _match_small_talk): a question that merely *opens* politely, like
# "Hi, why was my move a blunder?", must still reach real classification.
_SMALL_TALK_REPLIES = {
    "greeting": (
        "Hey! I'm here whenever you want to dig into your game — ask me about a "
        "specific move, a mistake, or the opening, and I'll walk you through it."
    ),
    "thanks": (
        "You're welcome! Happy to keep going whenever you want to look at another "
        "moment in the game."
    ),
    "farewell": "Good luck in your next game — come back any time you want to review it!",
}

_SMALL_TALK_PHRASES = {
    "greeting": {
        "hi", "hii", "hiya", "hello", "helo", "hey", "heya", "yo", "sup", "howdy",
        "good morning", "good afternoon", "good evening", "greetings",
        "how are you", "how are you doing", "how r u", "how are u", "hows it going",
        "how is it going", "whats up", "hi there", "hello there", "hey there",
    },
    "thanks": {
        "thanks", "thank you", "thanx", "thx", "ty", "cheers", "thanks a lot",
        "thank you so much", "thanks so much", "many thanks", "appreciate it",
        "ok thanks", "okay thanks", "great thanks", "cool thanks", "nice thanks",
        "got it thanks", "perfect thanks", "awesome thanks", "thanks buddy",
    },
    "farewell": {
        "bye", "byee", "goodbye", "good bye", "see you", "see ya", "cya",
        "good night", "goodnight", "gtg", "talk later", "see you later",
    },
}


def _match_small_talk(text: str) -> Optional[str]:
    """Returns a canned reply if the message is *purely* a greeting/thanks/farewell.

    Matches on the whole normalised message rather than a prefix, so genuine questions
    that happen to start politely still fall through to real intent classification.
    """
    normalised = re.sub(r"[^a-z\s]", "", (text or "").lower())
    normalised = re.sub(r"\s+", " ", normalised).strip()
    if not normalised:
        return None
    for category, phrases in _SMALL_TALK_PHRASES.items():
        if normalised in phrases:
            return _SMALL_TALK_REPLIES[category]
    return None


DISPATCH_END = "end"


def router_agent_node(state: CoachState) -> dict:
    """Decides, in a single visit, which specialists this turn needs.

    Entered exactly once per graph invocation. Because dispatch is always decided in one shot
    (one specialist, both in parallel, or neither), the specialists no longer loop back here,
    so there is no "what is left to run" state to track between visits.
    """
    logger.info("Running router_agent node")
    messages = state.get("messages", [])

    # Initial review: no conversation yet. Strategy always runs; rules deliberately does not,
    # since there is no rules question to answer on a plain game review. No LLM call.
    if not messages:
        return {
            "dispatch_targets": ["strategy"],
            "execution_logs": ["router_agent: Initial review — dispatching to strategy specialist (0 LLM calls)."],
            "agent_steps": [{
                "agent_name": "Router Agent",
                "prompt": "(Skipped — initial review, no user message)",
                "response": "strategy (fast-path default)"
            }]
        }

    # Pure small talk ("hi", "thanks") — answer from a template and end the turn here.
    # No LLM call, no specialist, and no grounding guard: a canned reply names no moves,
    # so there is nothing for the legality check to verify.
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if last_human is not None:
        canned = _match_small_talk(last_human.content)
        if canned:
            logger.info("Router matched small talk. Replying from template with 0 LLM calls.")
            return {
                "dispatch_targets": [DISPATCH_END],
                "output": canned,
                "messages": [AIMessage(content=canned)],
                "execution_logs": ["router_agent: Small talk matched. Canned reply, 0 LLM calls, skipped synthesis and grounding."],
                "agent_steps": [{
                    "agent_name": "Router Agent",
                    "prompt": f"(Deterministic small-talk match on: {last_human.content!r})",
                    "response": "small talk — canned reply, no LLM call"
                }]
            }

    # A real question: classify intent once. "both" fans out to the two specialists in parallel.
    llm_messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]
    for m in messages:
        if isinstance(m, HumanMessage):
            llm_messages.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            if not m.content.startswith("Grounding check:"):
                llm_messages.append({"role": "assistant", "content": m.content})

    prompt_str = "\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in llm_messages])

    try:
        response = chat(messages=llm_messages)
        choice = response.strip().lower()
        # Check "both" first: it contains neither substring, but an LLM may answer
        # "both" / "strategy and rules" / "rules and strategy" interchangeably.
        if "both" in choice or ("strategy" in choice and "rules" in choice):
            targets = ["strategy", "rules"]
        elif "strategy" in choice:
            targets = ["strategy"]
        elif "rules" in choice:
            targets = ["rules"]
        else:
            targets = []
    except Exception as e:
        logger.error(f"Router Agent LLM error: {e}")
        targets = []
        response = f"Failed with error: {e}"

    logger.info(f"Router Agent dispatching to: {targets or 'synthesizer only'}")
    return {
        "dispatch_targets": targets,
        "execution_logs": [f"router_agent: Classified intent. Dispatching to: {targets or ['synthesizer']}."],
        "agent_steps": [{
            "agent_name": "Router Agent",
            "prompt": prompt_str,
            "response": response
        }]
    }


def strategy_node(state: CoachState) -> dict:
    """Queries RAG strategies database and calls strategy specialist agent."""
    logger.info("Running strategy node")
    game = state.get("game")
    if state.get("messages"):
        query = state["messages"][-1].content
    elif game and game.opening_name:
        query = f"strategic themes and plans in the {game.opening_name}"
    else:
        query = "tactical themes"
    settings = get_settings()

    # Retrieve strategies context
    docs = retrieve_context(query, persist_dir=settings.chroma_db_path, limit=2, bucket="strategies")
    rag_context = "\n\n".join([doc["text"] for doc in docs])

    # Update rag_context in state for history and compatibility
    existing_rag = state.get("rag_context", "")
    new_rag = existing_rag + ("\n\n" if existing_rag else "") + rag_context

    analyses = state.get("analyses", [])
    move_analyses_summary = _build_move_analyses_summary(analyses)

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
    has_question = bool(state.get("messages"))
    query = state["messages"][-1].content if has_question else "laws of chess"
    settings = get_settings()

    # Retrieve rules context
    docs = retrieve_context(query, persist_dir=settings.chroma_db_path, limit=2, bucket="rules")
    rag_context = "\n\n".join([doc["text"] for doc in docs])

    # Update rag_context in state for history and compatibility
    existing_rag = state.get("rag_context", "")
    new_rag = existing_rag + ("\n\n" if existing_rag else "") + rag_context

    prompt_query = query if has_question else (
        "N/A — no specific rules question was asked; this is a general game review."
    )
    system_prompt = RULES_SYSTEM_PROMPT.format(
        rag_context=rag_context,
        query=prompt_query
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
    if rules_summary.strip() == "NO_RULES_QUESTION":
        rules_summary = "No rules themes analyzed."

    game = state.get("game")
    analyses = state.get("analyses", [])
    if game:
        game_context = (
            f"White: {game.white} | Black: {game.black} | Result: {game.result} | "
            f"Opening: {game.opening_name or 'Unknown'}"
        )
    else:
        game_context = "No game loaded."
    move_analyses_summary = _build_move_analyses_summary(analyses)

    system_prompt = SYNTHESIZER_SYSTEM_PROMPT.format(
        game_context=game_context,
        move_analyses_summary=move_analyses_summary,
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
        "execution_logs": ["synthesizer_node: Fused strategy and rules findings into final Markdown coaching overview."],
        "agent_steps": [{
            "agent_name": "Synthesizer Agent",
            "prompt": prompt_str,
            "response": output
        }]
    }


def should_delegate(state: CoachState):
    """Routes the router's one-shot decision to one specialist, both, or straight past them.

    Returning a *list* of node names is how LangGraph fans out to parallel branches: both
    specialists run in the same superstep, and because each has a fixed edge to
    synthesizer_node, LangGraph runs the synthesizer once, after both have finished.
    """
    targets = state.get("dispatch_targets") or []
    if DISPATCH_END in targets:
        # Router already wrote the canned small-talk reply — nothing to synthesise or ground.
        return END
    nodes = [t + "_node" for t in targets if t in ("strategy", "rules")]
    if not nodes:
        return "synthesizer_node"
    if len(nodes) == 1:
        return nodes[0]
    return nodes


def compile_coach_graph():
    """Compiles the rewired multi-agent Coach StateGraph workflow with MemorySaver."""
    workflow = StateGraph(CoachState)
    
    # Add nodes
    workflow.add_node("fetch_and_analyse", fetch_and_analyse_node)
    workflow.add_node("router_agent", router_agent_node)
    workflow.add_node("strategy_node", strategy_node)
    workflow.add_node("rules_node", rules_node)
    workflow.add_node("synthesizer_node", synthesizer_node)
    workflow.add_node("grounding_guard", grounding_guard_node)
    
    # Set execution edges
    workflow.set_entry_point("fetch_and_analyse")
    workflow.add_edge("fetch_and_analyse", "router_agent")
    
    # Router conditional edges
    workflow.add_conditional_edges(
        "router_agent",
        should_delegate,
        {
            "strategy_node": "strategy_node",
            "rules_node": "rules_node",
            "synthesizer_node": "synthesizer_node",
            END: END
        }
    )
    
    # Specialists go straight to synthesis. No loop back to the router: dispatch is decided in
    # one shot, so there is nothing left for a second router visit to decide. This is also what
    # makes the "both" case a real parallel fan-out/fan-in rather than a sequential chain.
    workflow.add_edge("strategy_node", "synthesizer_node")
    workflow.add_edge("rules_node", "synthesizer_node")
    
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
