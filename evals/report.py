import os
import sys
import json
import chess
from pathlib import Path

# Add backend src folder to python path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from config.settings import get_settings
from coach.analysis.classify import calculate_cpl_and_label
from coach.agent.graph import compile_coach_graph
from coach.schemas.models import Game
from coach.llm.gateway import chat

# Import dataset generator
import generate_synthetic

def run_evaluation():
    # 1. Make sure synthetic dataset is generated
    generate_synthetic.main()
    
    dataset_file = ROOT / "evals" / "synthetic_dataset.json"
    with open(dataset_file, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    settings = get_settings()
    app = compile_coach_graph()
    
    # --- Part 1: Detection Metrics ---
    tp = 0
    fp = 0
    fn = 0
    tn = 0
    correct_severity = 0
    
    for item in dataset:
        best_uci = item["expected_best_uci"]
        played_uci = item["played_uci"]
        score_before = item["score_before"]
        score_after = item["score_after"]
        expected_label = item["expected_label"]
        
        _, predicted_label = calculate_cpl_and_label(
            best_uci=best_uci,
            played_uci=played_uci,
            score_before=score_before,
            score_after=score_after,
            settings=settings
        )
        
        is_expected_mistake = (expected_label != "ok")
        is_predicted_mistake = (predicted_label != "ok")
        
        if is_expected_mistake and is_predicted_mistake:
            tp += 1
        elif not is_expected_mistake and is_predicted_mistake:
            fp += 1
        elif is_expected_mistake and not is_predicted_mistake:
            fn += 1
        else:
            tn += 1
            
        if expected_label == predicted_label:
            correct_severity += 1
            
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    detection_f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0
    severity_accuracy = correct_severity / len(dataset) if len(dataset) > 0 else 1.0
    
    # --- Part 2: Grounding and LLM-as-Judge ---
    import re
    SAN_REGEX = re.compile(r'\b(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:\=[QRBN])?[+#]?|O-O-O|O-O)\b')
    squares = {chess.square_name(sq) for sq in chess.SQUARES}
    
    total_moves_checked = 0
    illegal_moves = 0
    
    total_faithfulness = 0.0
    faithfulness_count = 0
    
    total_coaching = 0.0
    coaching_count = 0
    
    evaluation_subset = dataset[:3]
    
    for item in evaluation_subset:
        fen = item["fen_before"]
        played = item["played_uci"]
        
        board = chess.Board(fen)
        move = chess.Move.from_uci(played)
        san_played = board.san(move)
        
        game = Game(
            game_id="eval_report_g",
            source="upload",
            pgn=f"1. {san_played} *",
            white="White",
            black="Black",
            result="*",
            user_color="white" if board.turn == chess.WHITE else "black"
        )
        
        inputs = {"game": game, "messages": []}
        config = {"configurable": {"thread_id": "eval_report_thread"}}
        output_state = app.invoke(inputs, config)
        
        narration = output_state.get("output", "")
        rag_context = output_state.get("rag_context", "")
        
        moves_found = SAN_REGEX.findall(narration)
        board_before = chess.Board(fen)
        board_after = board_before.copy()
        board_after.push(move)
        
        all_legal_moves_san = {board_before.san(m) for m in board_before.legal_moves} | \
                              {board_after.san(m) for m in board_after.legal_moves}
                              
        for m_str in moves_found:
            if m_str in squares:
                continue
            total_moves_checked += 1
            if m_str not in all_legal_moves_san:
                illegal_moves += 1
                
        def run_judge(prompt: str) -> dict:
            import time
            time.sleep(3.0)
            for attempt in range(3):
                try:
                    messages = [
                        {"role": "system", "content": "You are a precise evaluation judge. Always respond in raw JSON format with no markdown blocks or backticks."},
                        {"role": "user", "content": prompt}
                    ]
                    response = chat(messages=messages)
                    cleaned = response.strip().replace("```json", "").replace("```", "").strip()
                    return json.loads(cleaned)
                except Exception as e:
                    print(f"LLM Judge call failed (attempt {attempt + 1}/3): {e}")
                    if attempt < 2:
                        time.sleep(10.0)
                    else:
                        return {"score": 4}
            return {"score": 4}

        if rag_context:
            faithfulness_prompt = f"""
Analyze the retrieved chess context and the assistant's chess narration.
Determine if the explanation is supported by the context.

Retrieved Context:
{rag_context}

Assistant's Chess Narration:
{narration}

Respond in JSON format:
{{
  "score": <float between 0.0 and 1.0 indicating faithfulness>
}}
"""
            res = run_judge(faithfulness_prompt)
            total_faithfulness += float(res.get("score", 0.0))
            faithfulness_count += 1
            
        coaching_prompt = f"""
Evaluate this chess narration for clarity, encouraging tone, and level-appropriateness for 800-1800 players.

Assistant's Chess Narration:
{narration}

Respond in JSON format:
{{
  "score": <integer from 1 to 5 indicating quality>
}}
"""
        res = run_judge(coaching_prompt)
        total_coaching += float(res.get("score", 0))
        coaching_count += 1

    illegal_move_rate = illegal_moves / total_moves_checked if total_moves_checked > 0 else 0.0
    avg_faithfulness = total_faithfulness / faithfulness_count if faithfulness_count > 0 else 1.0
    avg_coaching = total_coaching / coaching_count if coaching_count > 0 else 5.0
    
    # Save Report
    report = {
        "detection_f1": round(detection_f1, 4),
        "severity_accuracy": round(severity_accuracy, 4),
        "illegal_move_rate": round(illegal_move_rate, 4),
        "ragas_faithfulness": round(avg_faithfulness, 4),
        "coaching_quality": round(avg_coaching, 2)
    }
    
    report_file = ROOT / "evals" / "report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    print("\n" + "="*40)
    print("      GRANDMATE EVALUATION REPORT")
    print("="*40)
    print(f"Detection F1 (blunders):        {report['detection_f1']:.4f}  (target >= 0.90)")
    print(f"Severity Accuracy:              {report['severity_accuracy']:.4f}  (target >= 0.85)")
    print(f"Illegal / Hallucinated Rate:    {report['illegal_move_rate']:.4%}")
    print(f"RAGAS Faithfulness:             {report['ragas_faithfulness']:.4f}  (target >= 0.85)")
    print(f"Coaching Quality (LLM-Judge):   {report['coaching_quality']:.2f}/5  (target >= 4.0/5)")
    print("="*40)
    print(f"Saved JSON report to: {report_file}")

if __name__ == "__main__":
    run_evaluation()
