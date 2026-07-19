import pytest
from unittest.mock import patch, MagicMock, ANY
from coach.agent.graph import compile_coach_graph, should_delegate, DISPATCH_END
from langgraph.graph import END
from coach.schemas.models import Game, MoveAnalysis
from langchain_core.messages import HumanMessage, AIMessage

@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_router_delegates_to_rules(mock_chat, mock_retrieve_context):
    # One-shot dispatch: router classifies "rules", only rules_node runs, then synthesis.
    mock_chat.side_effect = [
        "rules",      # Router LLM decision
        "Stalemate is a draw according to FIDE rules.",  # Rules Specialist answer
        "Compiled response explaining stalemate rules." # Synthesizer answer
    ]
    
    mock_retrieve_context.return_value = [
        {
            "id": "rules_1",
            "text": "Stalemate occurs when the player to move has no legal moves and is not in check.",
            "metadata": {"bucket": "rules", "source": "FIDE_rules.pdf"}
        }
    ]
    
    graph = compile_coach_graph()
    
    inputs = {
        "messages": [HumanMessage(content="What is stalemate?")],
        "username": "user",
        "source": "upload",
        "pgn": "1. e4 e5 *",
        "game": Game(game_id="game_123", source="upload", pgn="1. e4 e5 *", white="magnus", black="hikaru", user_color="white", result="*"),
        "analyses": [],
        "rag_context": "",
        "output": ""
    }
    
    config = {"configurable": {"thread_id": "test_session_rules"}}
    final_state = graph.invoke(inputs, config=config)
    
    # Assertions
    assert "Stalemate" in final_state["rag_context"]
    assert final_state["output"] == "Compiled response explaining stalemate rules."
    
    # Verify that retrieve_context was called with bucket="rules"
    mock_retrieve_context.assert_any_call(
        "What is stalemate?",
        persist_dir=ANY,
        limit=2,
        bucket="rules"
    )


@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_router_delegates_to_strategy(mock_chat, mock_retrieve_context):
    # One-shot dispatch: router classifies "strategy", only strategy_node runs, then synthesis.
    mock_chat.side_effect = [
        "strategy",      # Router LLM decision
        "This move was a blunder because it drops the knight.",  # Strategy Specialist answer
        "Compiled tactical response." # Synthesizer answer
    ]
    
    mock_retrieve_context.return_value = [
        {
            "id": "strategy_1",
            "text": "Sicilian Defense is played with e4 c5.",
            "metadata": {"bucket": "strategies", "source": "tactics.md"}
        }
    ]
    
    graph = compile_coach_graph()
    
    inputs = {
        "messages": [HumanMessage(content="Why was my move a blunder?")],
        "username": "user",
        "source": "upload",
        "pgn": "1. e4 e5 *",
        "game": Game(game_id="game_123", source="upload", pgn="1. e4 e5 *", white="magnus", black="hikaru", user_color="white", result="*"),
        "analyses": [
            MoveAnalysis(ply=1, played_san="c5", best_san="Nf6", eval_before_cp=0, eval_after_cp=-200, centipawn_loss=200, label="blunder", theme="tactics", fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", played_uci="c7c5", best_uci="g8f6")
        ],
        "rag_context": "",
        "output": ""
    }
    
    config = {"configurable": {"thread_id": "test_session_strategy"}}
    final_state = graph.invoke(inputs, config=config)
    
    # Assertions
    assert "Sicilian" in final_state["rag_context"]
    assert final_state["output"] == "Compiled tactical response."
    
    # Verify retrieve_context was called with bucket="strategies"
    mock_retrieve_context.assert_any_call(
        "Why was my move a blunder?",
        persist_dir=ANY,
        limit=2,
        bucket="strategies"
    )


def test_should_delegate_helper():
    # should_delegate maps the router's one-shot decision onto the next node(s).
    assert should_delegate({"dispatch_targets": ["strategy"]}) == "strategy_node"
    assert should_delegate({"dispatch_targets": ["rules"]}) == "rules_node"
    assert should_delegate({"dispatch_targets": []}) == "synthesizer_node"
    assert should_delegate({}) == "synthesizer_node"

    # "both" returns a list - that is how LangGraph fans out to parallel branches.
    assert should_delegate({"dispatch_targets": ["strategy", "rules"]}) == ["strategy_node", "rules_node"]

    # small talk ends the turn without synthesis or grounding
    assert should_delegate({"dispatch_targets": [DISPATCH_END]}) == END


@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_router_defaults_to_strategy_on_initial_review(mock_chat, mock_retrieve_context):
    # messages=[] is what /review actually sends (backend/app.py) — this is the real bug path:
    # the router used to skip routing entirely here, so neither specialist ever ran.
    mock_chat.side_effect = [
        "Strategic findings for the position.",  # strategy_node
        "Compiled review response.",  # synthesizer_node
    ]
    mock_retrieve_context.return_value = [
        {"id": "s1", "text": "Sicilian Defense strategic ideas.",
         "metadata": {"bucket": "strategies", "source": "strategy.md"}}
    ]

    graph = compile_coach_graph()

    inputs = {
        "messages": [], "username": "user", "source": "upload", "pgn": "1. e4 e5 *",
        "game": Game(game_id="g1", source="upload", pgn="1. e4 e5 *", white="a", black="b",
                     user_color="white", result="*"),
        "analyses": [], "rag_context": "", "output": ""
    }
    final_state = graph.invoke(inputs, config={"configurable": {"thread_id": "test_initial_review"}})

    # strategy_findings/rules_findings are reset to None by synthesizer_node after use, so the
    # meaningful signal is that the run completed (no GraphRecursionError from the router
    # re-entering its own "no messages" branch forever) and that only strategy was queried.
    assert final_state["output"] == "Compiled review response."
    mock_retrieve_context.assert_any_call(ANY, persist_dir=ANY, limit=2, bucket="strategies")
    assert not any(
        call.kwargs.get("bucket") == "rules" for call in mock_retrieve_context.call_args_list
    )


def _greeting_inputs(message, thread):
    return {
        "messages": [HumanMessage(content=message)],
        "username": "user", "source": "upload", "pgn": "1. e4 e5 *",
        "game": Game(game_id="g1", source="upload", pgn="1. e4 e5 *", white="a", black="b",
                     user_color="white", result="*"),
        "analyses": [], "rag_context": "", "output": ""
    }, {"configurable": {"thread_id": thread}}


@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_small_talk_short_circuits_with_zero_llm_calls(mock_chat, mock_retrieve_context):
    # A bare greeting should never reach the LLM, a specialist, or the grounding guard.
    mock_retrieve_context.return_value = []
    graph = compile_coach_graph()

    inputs, config = _greeting_inputs("Hi", "test_small_talk_hi")
    final_state = graph.invoke(inputs, config=config)

    mock_chat.assert_not_called()
    mock_retrieve_context.assert_not_called()
    assert "dig into your game" in final_state["output"]
    # The canned reply must be the last AIMessage, since /chat reads the reply from there.
    assert isinstance(final_state["messages"][-1], AIMessage)
    assert final_state["messages"][-1].content == final_state["output"]


@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_polite_opener_still_reaches_classification(mock_chat, mock_retrieve_context):
    # Regression guard: the small-talk allowlist must not swallow a real question that
    # merely opens politely. This is the failure mode that would silently break coaching.
    # router classification -> strategy_node -> synthesizer (one-shot dispatch, no loop-back)
    mock_chat.side_effect = ["strategy", "Strategy findings.", "Compiled answer."]
    mock_retrieve_context.return_value = [
        {"id": "s1", "text": "Sicilian ideas.",
         "metadata": {"bucket": "strategies", "source": "strategy.md"}}
    ]
    graph = compile_coach_graph()

    inputs, config = _greeting_inputs("Hi, why was my move a blunder?", "test_polite_opener")
    final_state = graph.invoke(inputs, config=config)

    assert mock_chat.called, "a real question must still reach LLM classification"
    assert final_state["output"] == "Compiled answer."


@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_findings_persist_across_turns(mock_chat, mock_retrieve_context):
    # The synthesizer no longer wipes findings, so a review's strategy work stays available
    # as background context for later chat turns in the same thread.
    mock_chat.side_effect = ["Strategy findings.", "Review reply.", "strategy",
                             "Follow-up findings.", "Chat reply."]
    mock_retrieve_context.return_value = [
        {"id": "s1", "text": "ideas.", "metadata": {"bucket": "strategies", "source": "s.md"}}
    ]
    graph = compile_coach_graph()
    config = {"configurable": {"thread_id": "test_persist"}}

    review_inputs, _ = _greeting_inputs("ignored", "test_persist")
    review_inputs["messages"] = []
    review_state = graph.invoke(review_inputs, config=config)
    assert review_state["strategy_findings"] is not None, "review should produce findings"

    chat_state = graph.invoke({"messages": [HumanMessage(content="why was that bad?")]},
                              config=config)
    assert chat_state["strategy_findings"] is not None, "findings must survive the turn"


@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_router_runs_exactly_once_per_turn(mock_chat, mock_retrieve_context):
    # Proves the loop-back is gone: with it, the router was re-entered after each specialist.
    mock_chat.side_effect = ["Strategy findings.", "Review reply."]
    mock_retrieve_context.return_value = [
        {"id": "s1", "text": "ideas.", "metadata": {"bucket": "strategies", "source": "s.md"}}
    ]
    graph = compile_coach_graph()

    inputs, config = _greeting_inputs("ignored", "test_router_once")
    inputs["messages"] = []
    final_state = graph.invoke(inputs, config=config)

    router_steps = [s for s in final_state["agent_steps"] if s["agent_name"] == "Router Agent"]
    assert len(router_steps) == 1, f"router ran {len(router_steps)}x, expected once"


@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_both_specialists_dispatch_in_parallel(mock_chat, mock_retrieve_context):
    # A "both" classification fans out to the two specialists in a single superstep. Combined
    # with the router-runs-once assertion, both findings can only have come from one fan-out.
    mock_chat.side_effect = ["both", "Strategy findings.", "Rules findings.", "Combined reply."]
    mock_retrieve_context.return_value = [
        {"id": "x", "text": "ctx.", "metadata": {"bucket": "strategies", "source": "s.md"}}
    ]
    graph = compile_coach_graph()

    inputs, config = _greeting_inputs("was castling legal there, and was it a good idea?",
                                      "test_both_parallel")
    final_state = graph.invoke(inputs, config=config)

    assert final_state["strategy_findings"] is not None
    assert final_state["rules_findings"] is not None
    router_steps = [s for s in final_state["agent_steps"] if s["agent_name"] == "Router Agent"]
    assert len(router_steps) == 1, "both specialists must come from one fan-out, not a chain"
    buckets = [c.kwargs.get("bucket") for c in mock_retrieve_context.call_args_list]
    assert "strategies" in buckets and "rules" in buckets
