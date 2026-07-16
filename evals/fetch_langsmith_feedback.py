import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client

# Add backend src to system path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

def main():
    # Load environment variables
    backend_env = ROOT / "backend" / ".env"
    if backend_env.exists():
        load_dotenv(backend_env)
        
    api_key = os.environ.get("LANGCHAIN_API_KEY")
    project = os.environ.get("LANGCHAIN_PROJECT", "grandmate")
    
    if not api_key:
        print("Error: LANGCHAIN_API_KEY is not set in backend/.env or your environment.")
        return

    print(f"Connecting to LangSmith cloud API...")
    client = Client()
    
    try:
        print(f"Fetching latest feedback records for project '{project}'...")
        # Get latest 30 feedbacks
        feedbacks = list(client.list_feedback(project_name=project, limit=30))
        if not feedbacks:
            print("No feedback records found in LangSmith for this project.")
            return
            
        print(f"Retrieved {len(feedbacks)} feedback records. Grouping by run...")
        
        # Group feedback by run_id
        run_data = {}
        for fb in feedbacks:
            run_id = str(fb.run_id)
            if run_id not in run_data:
                run_data[run_id] = {
                    "faithfulness": None,
                    "coaching_quality": None,
                    "feedback_time": fb.created_at.strftime("%Y-%m-%d %H:%M:%S") if fb.created_at else "N/A"
                }
            if fb.key == "faithfulness":
                run_data[run_id]["faithfulness"] = fb.score
            elif fb.key == "coaching_quality":
                run_data[run_id]["coaching_quality"] = fb.score

        print("Fetching run details from LangSmith...")
        rows = []
        for run_id, metrics in run_data.items():
            try:
                run = client.read_run(run_id)
                # Parse inputs and outputs safely
                game_input = run.inputs.get("game", {})
                pgn = game_input.get("pgn", "N/A")
                user_color = game_input.get("user_color", "N/A")
                output_narration = run.outputs.get("output", "N/A") if run.outputs else "N/A"
                
                rows.append({
                    "run_id": run_id,
                    "pgn": pgn,
                    "user_color": user_color,
                    "output_narration": output_narration,
                    "faithfulness": metrics["faithfulness"],
                    "coaching_quality": metrics["coaching_quality"],
                    "time": metrics["feedback_time"]
                })
            except Exception as e:
                print(f"Warning: Could not read details for run {run_id}: {e}")

        # Safe statistics calculation
        faith_scores = [r["faithfulness"] for r in rows if r["faithfulness"] is not None]
        coach_scores = [r["coaching_quality"] for r in rows if r["coaching_quality"] is not None]

        avg_faith = round(sum(faith_scores) / len(faith_scores), 4) if faith_scores else "N/A"
        avg_coach = round(sum(coach_scores) / len(coach_scores), 2) if coach_scores else "N/A"

        faith_status = "N/A"
        if avg_faith != "N/A":
            faith_status = "✅ Passed" if avg_faith >= 0.85 else "❌ Failed"

        coach_status = "N/A"
        if avg_coach != "N/A":
            coach_status = "✅ Passed" if avg_coach >= 4.0 else "❌ Failed"

        # Compile Markdown Report
        md_content = f"""# LangSmith Cloud Evaluation Report — Grandmate

This report compiles evaluation scores fetched directly from the **LangSmith** cloud platform. These scores represent LLM-as-judge feedback evaluated on live/test runs of the Grandmate coach graph.

* **Project Name:** `{project}`
* **Last Updated:** {rows[0]['time'] if rows else 'N/A'} (UTC)

---

## 1. Aggregated Averages
| Metric | Count | Average Score | Target | Status |
| :--- | :---: | :---: | :---: | :---: |
| **RAGAS Faithfulness** | {len(faith_scores)} | {avg_faith} | `≥ 0.85` | {faith_status} |
| **Coaching Quality** | {len(coach_scores)} | {avg_coach} / 5 | `≥ 4.0` | {coach_status} |

---

## 2. Detailed Run Invocations & Judge Feedback

"""
        for index, r in enumerate(rows, 1):
            md_content += f"""### Run #{index}: {r['run_id']}
* **Timestamp:** `{r['time']}`
* **User Side:** `{r['user_color'].upper()}`
* **Game PGN:** `{r['pgn']}`
* **Scores:**
  - **Faithfulness:** `{r['faithfulness'] if r['faithfulness'] is not None else 'N/A'}` (Target `≥ 0.85`)
  - **Coaching Quality:** `{r['coaching_quality'] if r['coaching_quality'] is not None else 'N/A'}/5` (Target `≥ 4.0/5`)

#### Narration Output:
> {r['output_narration'].replace(chr(10), chr(10) + '> ')}

---
"""

        report_file = ROOT / "final_docs" / "langsmith_evaluation_report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"Successfully generated LangSmith evaluation report at: {report_file}")
        
    except Exception as e:
        print(f"Error executing LangSmith fetch: {e}")

if __name__ == "__main__":
    main()
