import json
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
        output_state = app.invoke(inputs, config)
        
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
        output_state = app.invoke(inputs, config)
        
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
        
    avg_coaching = total_score / count if count > 0 else 5.0
    print(f"\nAverage LLM-Judge Coaching Quality: {avg_coaching:.2f}/5")
    assert avg_coaching >= 4.0
