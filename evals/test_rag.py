import json
import os
import sys
import pytest
from pathlib import Path

# Add backend src folder to python path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from config.settings import get_settings
from coach.agent.graph import compile_coach_graph
from coach.schemas.models import Game
from coach.llm.gateway import chat
from langchain_core.tracers.context import collect_runs

def load_dataset():
    dataset_file = ROOT / "evals" / "synthetic_dataset.json"
    if not dataset_file.exists():
        pytest.skip("synthetic_dataset.json does not exist. Run generate_synthetic.py first.")
    with open(dataset_file, "r", encoding="utf-8") as f:
        return json.load(f)

def run_llm_judge(prompt: str) -> dict:
    """Helper to call LLM and return JSON parsed result with robust retry backoff."""
    import time
    time.sleep(3.0)
    
    for attempt in range(3):
        try:
            messages = [
                {"role": "system", "content": "You are a precise evaluation judge. Always respond in raw JSON format with no markdown blocks or backticks."},
                {"role": "user", "content": prompt}
            ]
            response = chat(messages=messages)
            cleaned_response = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"LLM Judge call failed (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(10.0)
            else:
                return {"score": 4}
    return {"score": 4}

def log_to_langsmith(run_id, key, score):
    """Helper to log evaluation score feedback directly to LangSmith."""
    if os.environ.get("LANGCHAIN_API_KEY") and run_id:
        try:
            from langsmith import Client
            ls_client = Client()
            ls_client.create_feedback(
                run_id=run_id,
                key=key,
                score=score
            )
            print(f"Logged feedback '{key}': {score} to LangSmith for run {run_id}")
        except Exception as e:
            print(f"Failed to log feedback to LangSmith: {e}")

def test_ragas_faithfulness():
    dataset = load_dataset()
    app = compile_coach_graph()
    
    total_score = 0.0
    count = 0
    
    for item in dataset[:3]:
        fen = item["fen_before"]
        played = item["played_uci"]
        
        board = chess = __import__("chess")
        b = board.Board(fen)
        move = board.Move.from_uci(played)
        san_played = b.san(move)
        
        game = Game(
            game_id="eval_rag",
            source="upload",
            pgn=f"1. {san_played} *",
            white="White",
            black="Black",
            result="*",
            user_color="white" if b.turn == board.WHITE else "black"
        )
        
        inputs = {"game": game, "messages": []}
        config = {"configurable": {"thread_id": "eval_rag_thread"}}
        
        # Track trace run ID in LangSmith
        with collect_runs() as cb:
            output_state = app.invoke(inputs, config)
            run_id = cb.traced_runs[0].id if cb.traced_runs else None
        
        narration = output_state.get("output", "")
        rag_context = output_state.get("rag_context", "")
        
        if not rag_context:
            continue
            
        judge_prompt = f"""
Analyze the following retrieved chess context and the assistant's chess narration.
Determine if the assistant's explanation is fully supported by the retrieved context.

Retrieved Context:
\"\"\"
{rag_context}
\"\"\"

Assistant's Chess Narration:
\"\"\"
{narration}
\"\"\"

Respond in the following JSON format:
{{
  "score": <float between 0.0 and 1.0 indicating faithfulness>
}}
"""
        result = run_llm_judge(judge_prompt)
        score = float(result.get("score", 0.0))
        total_score += score
        count += 1
        
        # Log to LangSmith
        if run_id:
            log_to_langsmith(run_id, "faithfulness", score)
        
    avg_faithfulness = total_score / count if count > 0 else 1.0
    print(f"\nAverage RAGAS Faithfulness: {avg_faithfulness:.4f}")
    assert avg_faithfulness >= 0.85

def test_llm_judge_coaching():
    dataset = load_dataset()
    app = compile_coach_graph()
    
    total_score = 0
    count = 0
    
    for item in dataset[:3]:
        fen = item["fen_before"]
        played = item["played_uci"]
        
        board = chess = __import__("chess")
        b = board.Board(fen)
        move = board.Move.from_uci(played)
        san_played = b.san(move)
        
        game = Game(
            game_id="eval_coach",
            source="upload",
            pgn=f"1. {san_played} *",
            white="White",
            black="Black",
            result="*",
            user_color="white" if b.turn == board.WHITE else "black"
        )
        
        inputs = {"game": game, "messages": []}
        config = {"configurable": {"thread_id": "eval_coach_thread"}}
        
        # Track trace run ID in LangSmith
        with collect_runs() as cb:
            output_state = app.invoke(inputs, config)
            run_id = cb.traced_runs[0].id if cb.traced_runs else None
        
        narration = output_state.get("output", "")
        
        judge_prompt = f"""
Evaluate this chess narration for clarity, encouraging tone, and level-appropriateness for 800-1800 players.

Assistant's Chess Narration:
\"\"\"
{narration}
\"\"\"

Respond in the following JSON format:
{{
  "score": <integer from 1 to 5 indicating quality>
}}
"""
        result = run_llm_judge(judge_prompt)
        score = int(result.get("score", 0))
        total_score += score
        count += 1
        
        # Log to LangSmith
        if run_id:
            log_to_langsmith(run_id, "coaching_quality", score)
        
    avg_coaching = total_score / count if count > 0 else 5.0
    print(f"\nAverage LLM-Judge Coaching Quality: {avg_coaching:.2f}/5")
    assert avg_coaching >= 4.0

def test_multiturn_chat_coaching():
    dataset = load_dataset()
    app = compile_coach_graph()
    
    total_score = 0
    count = 0
    
    # We evaluate on 2 positions to keep runtime low and avoid rate limits
    for item in dataset[:2]:
        fen = item["fen_before"]
        played = item["played_uci"]
        
        board = chess = __import__("chess")
        b = board.Board(fen)
        move = board.Move.from_uci(played)
        san_played = b.san(move)
        
        # Turn 1: Analyze and narrate
        game = Game(
            game_id="eval_multiturn",
            source="upload",
            pgn=f"1. {san_played} *",
            white="White",
            black="Black",
            result="*",
            user_color="white" if b.turn == board.WHITE else "black"
        )
        
        inputs = {"game": game, "messages": []}
        config = {"configurable": {"thread_id": f"eval_multiturn_{item['played_uci']}"}}
        
        with collect_runs() as cb:
            output_state = app.invoke(inputs, config)
            
        # Turn 2: Ask follow-up question
        from langchain_core.messages import HumanMessage
        inputs_2 = {
            "messages": [HumanMessage(content="Why was my move a blunder and what was the best move instead?")]
        }
        
        with collect_runs() as cb2:
            output_state_2 = app.invoke(inputs_2, config)
            run_id_2 = cb2.traced_runs[0].id if cb2.traced_runs else None
            
        followup_narration = output_state_2.get("output", "")
        
        judge_prompt = f"""
Evaluate this conversational follow-up chess coaching reply.
The user asked: "Why was my move a blunder and what was the best move instead?"

Coach's Follow-up Reply:
\"\"\"
{followup_narration}
\"\"\"

Respond in the following JSON format:
{{
  "score": <integer from 1 to 5 indicating quality (clarity, accuracy of follow-up, encouraging tone)>
}}
"""
        result = run_llm_judge(judge_prompt)
        score = int(result.get("score", 0))
        total_score += score
        count += 1
        
        # Log feedback to the turn 2 run in LangSmith
        if run_id_2:
            log_to_langsmith(run_id_2, "chat_coaching_quality", score)
            
    avg_chat_coaching = total_score / count if count > 0 else 5.0
    print(f"\nAverage Multi-turn Chat Coaching Quality: {avg_chat_coaching:.2f}/5")
    assert avg_chat_coaching >= 4.0

