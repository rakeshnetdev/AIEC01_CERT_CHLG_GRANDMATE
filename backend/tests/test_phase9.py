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
