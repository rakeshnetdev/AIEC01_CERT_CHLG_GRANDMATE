import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app import app
from coach.schemas.models import CoachReport

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("coach.agent.graph.engine_eval")
@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_review_endpoint(mock_chat, mock_retrieve_context, mock_engine_eval):
    # 1. Setup mock behaviors
    mock_engine_eval.side_effect = [
        {"best_uci": "e2e4", "pv_uci": ["e2e4"], "score_cp": 35},  # ply 1
    ]
    mock_retrieve_context.return_value = []
    mock_chat.return_value = "Great opening selection with e4. Keep it up!"
    
    # 2. Call POST /review with a direct PGN
    pgn_input = '[White "magnus"]\n[Black "hikaru"]\n[Opening "Sicilian Defense"]\n[Result "*"]\n\n1. e4 c5 *'
    payload = {
        "username": "magnus",
        "source": "lichess",
        "pgn": pgn_input,
        "max_games": 1
    }
    
    response = client.post("/review", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["username"] == "magnus"
    assert "e4" in data["summary"]
    assert data["games_reviewed"] == 1
    assert "findings" in data
    assert "top_weaknesses" in data
    assert "drills" in data


def test_guardrails_input_refusal():
    # 1. Chat input requesting code
    chat_payload = {
        "message": "Write a python script to reverse a string.",
        "session_id": "test_session_1"
    }
    response = client.post("/chat", json=chat_payload)
    assert response.status_code == 400
    assert "Programming/code requests are not allowed" in response.json()["detail"]
    
    # 2. Review input requesting off-topic
    review_payload = {
        "username": "how to bake a chocolate cake",
        "source": "lichess",
        "max_games": 1
    }
    response = client.post("/review", json=review_payload)
    assert response.status_code == 400
    assert "Please ask chess-related questions" in response.json()["detail"]


@patch("coach.agent.graph.engine_eval")
@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_guardrails_output_moderation(mock_chat, mock_retrieve_context, mock_engine_eval):
    # Setup mock to return a profane response
    mock_engine_eval.side_effect = [
        {"best_uci": "e2e4", "pv_uci": ["e2e4"], "score_cp": 35},
    ]
    mock_retrieve_context.return_value = []
    mock_chat.return_value = "This move was total profane trash."  # triggered word: profane
    
    pgn_input = '[White "magnus"]\n[Black "hikaru"]\n[Opening "Sicilian Defense"]\n[Result "*"]\n\n1. e4 c5 *'
    payload = {
        "username": "magnus",
        "source": "lichess",
        "pgn": pgn_input,
        "max_games": 1
    }
    
    response = client.post("/review", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Narration should be moderated
    assert "[Moderated Response]" in data["summary"]


def test_praggnanandhaa_pgn_validation():
    from coach.guardrails import validate_request
    pgn_input = """[Event "34th TCh-IND 2014"]
[Site "Kanpur IND"]
[Date "2014.02.14"]
[Round "1.2"]
[White "Thejkumar,M"]
[Black "Praggnanandhaa,R"]
[Result "1-0"]
[WhiteElo "2474"]
[BlackElo "1974"]
[ECO "D37"]

1.d4 d5 2.c4 e6 3.Nf3 Nf6 4.Nc3 Be7 5.Bf4 c6 6.e3 O-O 7.Rc1 b6 8.Bd3 Bb7
9.O-O Nbd7 10.Qe2 c5 11.Rfd1 Ne4 12.cxd5 exd5 13.Ba6 Nxc3 14.Rxc3 Qc8 15.Bxb7 Qxb7
16.dxc5 Nxc5 17.Be5 Rac8 18.Nd4 Nd7 19.Bxg7 Kxg7 20.Qg4+ Kh8 21.Nf5 Rg8 22.Rxc8 Qxc8
23.Nxe7 Rxg4 24.Nxc8 Nf6 25.b3 Rg8 26.Rc1 Kg7 27.Nxa7 Ra8 28.Rc7 Ne4 29.b4 Nd2
30.g3 Nf3+ 31.Kg2 Ne1+ 32.Kf1 Nd3 33.a3 Kf6 34.Rb7 Kg7 35.Nb5 Nb2 36.Rxb6 Nc4
37.Rb7 Nxa3 38.Nd6 Rf8 39.b5 Kf6 40.b6 Ke6 41.Nxf7 Nc4 42.Ng5+ Kf5 43.Nxh7 Rh8
44.h4 Kg6 45.Ng5 Rf8 46.Ne6 Rf6 47.Nf4+ Kf5 48.Nxd5 Rd6 49.Rc7 Nxb6 50.Nxb6 Rxb6
51.Kg2 Kg4 52.Rc5 Rg6 53.f3+  1-0"""
    # Should pass without raising ValueError
    validate_request(pgn_input)


@patch("coach.agent.graph.engine_eval")
@patch("coach.agent.graph.retrieve_context")
@patch("coach.agent.graph.chat")
def test_review_and_chat_session_continuity(mock_chat, mock_retrieve_context, mock_engine_eval):
    # Mock behaviors
    mock_engine_eval.side_effect = [
        {"best_uci": "e2e4", "pv_uci": ["e2e4"], "score_cp": 35},
    ]
    mock_retrieve_context.return_value = []
    mock_chat.side_effect = [
        "Welcome! e4 is great.", # Response for review
        "The weaknesses are..." # Response for follow-up chat
    ]
    
    session_id = "test_shared_session_123"
    pgn_input = '[White "magnus"]\n[Black "hikaru"]\n[Opening "Sicilian Defense"]\n[Result "*"]\n\n1. e4 c5 *'
    
    # 1. First run /review with session_id
    payload = {
        "username": "magnus",
        "source": "lichess",
        "pgn": pgn_input,
        "max_games": 1,
        "session_id": session_id
    }
    
    response = client.post("/review", json=payload)
    assert response.status_code == 200
    assert response.json()["username"] == "magnus"
    
    # 2. Call /chat with the SAME session_id
    chat_payload = {
        "message": "explain me the focus weaknesses in the play",
        "session_id": session_id
    }
    response = client.post("/chat", json=chat_payload)
    assert response.status_code == 200
    assert "weaknesses" in response.json()["reply"]


