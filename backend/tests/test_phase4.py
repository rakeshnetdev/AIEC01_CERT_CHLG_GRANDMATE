import pytest
from unittest.mock import patch, MagicMock
from coach.agent.graph import compile_coach_graph
from coach.schemas.models import Game

@patch("coach.agent.graph.engine_eval")
@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_coach_agent_e2e(mock_chat, mock_retrieve_context, mock_engine_eval):
    # 1. Setup mock behaviors
    mock_engine_eval.side_effect = [
        {"best_uci": "e2e4", "pv_uci": ["e2e4"], "score_cp": 35},  # ply 1
        {"best_uci": "e7e5", "pv_uci": ["e7e5"], "score_cp": -20},  # ply 1 after (skipped)
    ]
    
    mock_retrieve_context.return_value = [
        {
            "id": "opening_0",
            "text": "Opening: Sicilian Defense. Moves: e4 c5. Description: A fighting defense.",
            "metadata": {"type": "opening", "name": "Sicilian Defense"}
        }
    ]
    
    mock_chat.return_value = "Hello! In your game, you played the Sicilian Defense. That is an excellent fighting choice. Your Stockfish evaluation was +35."
    
    # 2. Compile the Graph
    graph = compile_coach_graph()
    assert graph is not None
    
    # 3. Invoke the Graph
    pgn_with_headers = '[White "magnus"]\n[Black "hikaru"]\n[Opening "Sicilian Defense"]\n[Result "*"]\n\n1. e4 c5 *'
    inputs = {
        "messages": [],
        "username": "magnus",
        "source": "lichess",
        "pgn": pgn_with_headers,
        "game": None,
        "analyses": [],
        "rag_context": "",
        "output": ""
    }
    
    config = {"configurable": {"thread_id": "test_session_123"}}
    final_state = graph.invoke(inputs, config=config)
    
    # 4. Assertions on final state
    assert final_state["game"] is not None
    assert isinstance(final_state["game"], Game)
    assert final_state["game"].white == "magnus" or final_state["game"].black == "magnus"
    
    assert len(final_state["analyses"]) > 0
    assert "Sicilian Defense" in final_state["rag_context"]
    assert "Sicilian Defense" in final_state["output"]
    assert "Stockfish" in final_state["output"]
    
    # 5. Verify Mock Calls
    mock_retrieve_context.assert_called()
    mock_chat.assert_called()
