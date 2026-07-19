import pytest
from unittest.mock import patch, MagicMock, ANY
from coach.agent.graph import compile_coach_graph, should_delegate
from coach.schemas.models import Game, MoveAnalysis
from langchain_core.messages import HumanMessage, AIMessage

@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_router_delegates_to_rules(mock_chat, mock_retrieve_context):
    # Router picks 'rules' first, then fast-paths to strategy, then synthesizer
    mock_chat.side_effect = [
        "rules",      # Router LLM decision
        "Stalemate is a draw according to FIDE rules.",  # Rules Specialist answer
        "Strategy analysis for the position.",  # Strategy Specialist answer (auto-chained)
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
    # Router picks 'strategy' first, then fast-paths to rules, then synthesizer
    mock_chat.side_effect = [
        "strategy",      # Router LLM decision
        "This move was a blunder because it drops the knight.",  # Strategy Specialist answer
        "Rules analysis for the position.",  # Rules Specialist answer (auto-chained)
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
    # Test should_delegate edge routing function
    state_strategy = {"delegated_specialist": "strategy"}
    assert should_delegate(state_strategy) == "strategy_node"

    state_rules = {"delegated_specialist": "rules"}
    assert should_delegate(state_rules) == "rules_node"

    state_none = {"delegated_specialist": None}
    assert should_delegate(state_none) == "synthesizer_node"


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
    # router classification -> strategy_node -> (loop-back fast-path) rules_node -> synthesizer.
    # The rules hop is today's sequential loop-back behaviour; step 4 replaces it.
    mock_chat.side_effect = ["strategy", "Strategy findings.", "Rules findings.", "Compiled answer."]
    mock_retrieve_context.return_value = [
        {"id": "s1", "text": "Sicilian ideas.",
         "metadata": {"bucket": "strategies", "source": "strategy.md"}}
    ]
    graph = compile_coach_graph()

    inputs, config = _greeting_inputs("Hi, why was my move a blunder?", "test_polite_opener")
    final_state = graph.invoke(inputs, config=config)

    assert mock_chat.called, "a real question must still reach LLM classification"
    assert final_state["output"] == "Compiled answer."
