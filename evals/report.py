"""Grandmate evaluation harness.

Consumes the oracle-labelled dataset from ``generate_synthetic.py`` and measures the
production system against it. See final_docs/synthetic_data_and_eval_design.md.

Two layers with very different economics:

  * **Deterministic layer** (default, free): runs the *production* engine at
    ``settings.engine_depth`` and the *production* classifier over the full dataset, and
    compares the result against the deep-oracle ground truth. This can genuinely fail --
    corrupt the thresholds and the F1 drops.
  * **Judged layer** (``--llm``, costs money): drives the real LangGraph pipeline and uses
    an LLM judge for faithfulness and coaching quality.

Harness rules enforced here (each one is a defect the previous version shipped):
  1. Ground truth is never produced by the code under test.
  2. No metric defaults to a passing value. A failed measurement is reported as
     ``null`` / "not measured", never as 1.0 or 4.
  3. Every metric reports its sample count ``n``.
  4. Positions are reconstructed from ``fen_before`` via SetUp/FEN headers -- never by
     replaying a move from the standard starting position.

Usage:
    cd backend && uv run python ../evals/report.py             # deterministic only (free)
    cd backend && uv run python ../evals/report.py --llm       # + judged metrics (paid)
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chess

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from config.settings import get_settings
from coach.analysis.classify import calculate_cpl_and_label   # the code UNDER TEST
from coach.analysis.engine import Engine

SAN_REGEX = re.compile(r'\b(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:\=[QRBN])?[+#]?|O-O-O|O-O)\b')
MISTAKE_LABELS = {"inaccuracy", "mistake", "blunder"}


# --------------------------------------------------------------------------------------
# Deterministic layer: production engine + production classifier vs. the oracle
# --------------------------------------------------------------------------------------

def evaluate_detection(dataset: List[Dict], settings) -> Dict:
    """Run the production configuration over every row and score it against the oracle.

    Crucially this re-analyses each position with the *production* engine depth rather than
    reusing the oracle's stored scores. Reusing them would feed the classifier the same
    inputs its ground truth came from, which is how the previous harness guaranteed 100%.
    """
    tp = fp = fn = tn = 0
    correct_severity = 0
    rows: List[Dict] = []

    with Engine.from_settings(settings) as engine:
        for i, item in enumerate(dataset, 1):
            fen_before = item["fen_before"]
            fen_after = item["fen_after"]
            played_uci = item["played_uci"]

            # Production analysis at production depth (settings.engine_depth).
            ev_before = engine.analyse_fen(fen_before, depth=settings.engine_depth)
            ev_after = engine.analyse_fen(fen_after, depth=settings.engine_depth)

            predicted_cpl, predicted_label = calculate_cpl_and_label(
                best_uci=ev_before.best_uci,
                played_uci=played_uci,
                score_before=ev_before.score_cp,
                score_after=ev_after.score_cp,
                settings=settings,
            )

            expected_label = item["expected_label"]
            exp_mistake = expected_label in MISTAKE_LABELS
            pred_mistake = predicted_label in MISTAKE_LABELS

            if exp_mistake and pred_mistake:
                tp += 1
            elif not exp_mistake and pred_mistake:
                fp += 1
            elif exp_mistake and not pred_mistake:
                fn += 1
            else:
                tn += 1

            if expected_label == predicted_label:
                correct_severity += 1

            rows.append({
                **{k: item[k] for k in ("id", "phase", "side_to_move", "nature", "edge",
                                        "played_san", "expected_label", "oracle_cpl")},
                "predicted_label": predicted_label,
                "predicted_cpl": predicted_cpl,
                "agree": expected_label == predicted_label,
            })
            if i % 20 == 0:
                print(f"    ...{i}/{len(dataset)} positions analysed")

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "n": len(dataset),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": precision,
        "recall": recall,
        "detection_f1": f1,
        "severity_accuracy": correct_severity / len(dataset) if dataset else None,
        "rows": rows,
    }


def slice_report(rows: List[Dict], key: str) -> Dict[str, str]:
    """Per-scenario agreement, so a failure can be localised instead of averaged away."""
    buckets: Dict[str, List[bool]] = {}
    for r in rows:
        k = str(r.get(key))
        if k == "None":
            continue
        buckets.setdefault(k, []).append(r["agree"])
    return {
        k: f"{sum(v)}/{len(v)} ({100.0 * sum(v) / len(v):.0f}%)"
        for k, v in sorted(buckets.items())
    }


# --------------------------------------------------------------------------------------
# Judged layer
# --------------------------------------------------------------------------------------

def game_from_fen(fen: str, san: str):
    """Build a Game from an arbitrary FEN using SetUp/FEN headers.

    The previous harness used ``pgn=f"1. {san} *"``, which discarded the FEN, analysed
    mid-game positions from the starting board, and produced an *illegal* PGN for every
    black-to-move position (silently dropping them).
    """
    from coach.ingestion.pgn import parse_pgn

    board = chess.Board(fen)
    is_white = board.turn == chess.WHITE
    movetext = f"1. {san} *" if is_white else f"1... {san} *"
    white = "evaluser" if is_white else "Opponent"
    black = "Opponent" if is_white else "evaluser"
    pgn = (
        f'[Event "eval"]\n[Site "eval"]\n[Date "????.??.??"]\n[Round "-"]\n'
        f'[White "{white}"]\n[Black "{black}"]\n[Result "*"]\n'
        f'[SetUp "1"]\n[FEN "{fen}"]\n\n{movetext}'
    )
    return parse_pgn(pgn, "upload", "evaluser")


def run_judge(prompt: str) -> Optional[dict]:
    """Ask the judge for a JSON verdict. Returns None on failure -- never a passing default.

    The previous implementation returned ``{"score": 4}`` after three failures, so a total
    judge outage was published as 'coaching quality 4.0/5 -- target met'.
    """
    from coach.llm.gateway import chat

    for attempt in range(3):
        try:
            time.sleep(2.0)
            response = chat(messages=[
                {"role": "system", "content": "You are a precise evaluation judge. "
                                              "Always respond in raw JSON with no markdown or backticks."},
                {"role": "user", "content": prompt},
            ])
            cleaned = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except Exception as exc:
            print(f"      judge call failed (attempt {attempt + 1}/3): {exc}")
            if attempt < 2:
                time.sleep(8.0)
    return None


def check_move_legality(narration: str, fen_before: str, played_uci: str) -> Tuple[int, int]:
    """Return (moves_checked, illegal_moves) for SAN tokens named in the narration."""
    board_before = chess.Board(fen_before)
    board_after = board_before.copy()
    board_after.push(chess.Move.from_uci(played_uci))

    legal_san = {board_before.san(m) for m in board_before.legal_moves} | \
                {board_after.san(m) for m in board_after.legal_moves}
    # Piece-square descriptions (e.g. "Bc4") are prose, not move claims.
    for sq in chess.SQUARES:
        piece = board_before.piece_at(sq)
        if piece:
            legal_san.add(f"{piece.symbol().upper()}{chess.square_name(sq)}")

    squares = {chess.square_name(sq) for sq in chess.SQUARES}
    checked = illegal = 0
    for token in SAN_REGEX.findall(narration):
        if token in squares:
            continue
        checked += 1
        if token not in legal_san:
            illegal += 1
    return checked, illegal


def evaluate_judged(dataset: List[Dict], sample: int) -> Dict:
    """Drive the real pipeline and judge its narration. Costs money."""
    from coach.agent.graph import compile_coach_graph

    app = compile_coach_graph()

    # Prefer rows that actually produce coaching narration (real mistakes), and spread
    # across scenarios rather than taking the first N.
    mistakes = [r for r in dataset if r["expected_label"] in MISTAKE_LABELS]
    subset = (mistakes or dataset)[:sample]

    total_checked = total_illegal = 0
    faithfulness: List[float] = []
    coaching: List[float] = []
    judge_failures = 0
    pipeline_failures = 0
    no_context = 0

    for i, item in enumerate(subset, 1):
        print(f"  [{i}/{len(subset)}] {item['played_san']} ({item['expected_label']}, "
              f"{item['side_to_move']} to move)")
        try:
            game = game_from_fen(item["fen_before"], item["played_san"])
            state = app.invoke({"game": game, "messages": []},
                               {"configurable": {"thread_id": f"eval_{item['id']}"}})
        except Exception as exc:
            print(f"      pipeline FAILED: {exc}")
            pipeline_failures += 1
            continue

        narration = state.get("output", "") or ""
        rag_context = state.get("rag_context", "") or ""
        analyses = state.get("analyses") or []

        checked, illegal = check_move_legality(narration, item["fen_before"], item["played_uci"])
        total_checked += checked
        total_illegal += illegal

        # Engine facts belong in the grounding set. Golden Rule 1 REQUIRES the coach to
        # narrate Stockfish-derived facts, which by definition are absent from the RAG
        # corpus -- judging them against RAG alone penalises correct behaviour.
        engine_facts = "\n".join(
            f"- Move {a.played_san}: best was {a.best_san}, eval {a.eval_before_cp} -> "
            f"{a.eval_after_cp} cp, loss {a.centipawn_loss}, severity {a.label}."
            for a in analyses
        ) or "- (no engine analysis available)"

        if rag_context.strip():
            verdict = run_judge(f"""You are judging FAITHFULNESS of a chess coach's narration.

The narration is allowed to state the ENGINE FACTS below (they are verified ground truth).
It is also allowed to draw on the RETRIEVED THEORY below.
Score how well the narration is supported by these two sources combined. Penalise only
claims that contradict them or are invented outright.

ENGINE FACTS (verified):
{engine_facts}

RETRIEVED THEORY:
{rag_context}

NARRATION:
{narration}

Respond in JSON: {{"score": <float 0.0-1.0>}}""")
            if verdict is None or "score" not in verdict:
                judge_failures += 1
            else:
                faithfulness.append(float(verdict["score"]))
        else:
            # Not a pass. No context retrieved means the metric was not measurable here.
            no_context += 1

        verdict = run_judge(f"""Evaluate this chess narration for clarity, encouraging tone, and
level-appropriateness for 800-1800 rated players.

NARRATION:
{narration}

Respond in JSON: {{"score": <integer 1-5>}}""")
        if verdict is None or "score" not in verdict:
            judge_failures += 1
        else:
            coaching.append(float(verdict["score"]))

    return {
        "n_attempted": len(subset),
        "pipeline_failures": pipeline_failures,
        "judge_failures": judge_failures,
        "rows_without_rag_context": no_context,
        "illegal_move_rate": (total_illegal / total_checked) if total_checked else None,
        "moves_checked": total_checked,
        "ragas_faithfulness": (sum(faithfulness) / len(faithfulness)) if faithfulness else None,
        "faithfulness_n": len(faithfulness),
        "coaching_quality": (sum(coaching) / len(coaching)) if coaching else None,
        "coaching_n": len(coaching),
    }


# --------------------------------------------------------------------------------------

def fmt(value, spec: str = ".4f") -> str:
    return "not measured" if value is None else format(value, spec)


def main() -> None:
    parser = argparse.ArgumentParser(description="Grandmate evaluation harness.")
    parser.add_argument("--llm", action="store_true",
                        help="Also run judged metrics (makes paid LLM calls).")
    parser.add_argument("--sample", type=int, default=3,
                        help="Positions to drive through the pipeline for judged metrics.")
    parser.add_argument("--no-save", action="store_true",
                        help="Print results without writing report.json. Use this for "
                             "falsification runs (e.g. corrupted thresholds), so an "
                             "intentionally-broken run cannot overwrite the real report.")
    args = parser.parse_args()

    dataset_file = ROOT / "evals" / "synthetic_dataset.json"
    if not dataset_file.exists():
        raise SystemExit(f"No dataset at {dataset_file}. Run generate_synthetic.py first.")
    dataset = json.loads(dataset_file.read_text(encoding="utf-8"))
    if not dataset:
        raise SystemExit("Dataset is empty.")

    oracle_depth = dataset[0].get("oracle_depth")
    if oracle_depth is None:
        raise SystemExit(
            "Dataset has no 'oracle_depth' -- it predates the independent-oracle rewrite and "
            "its labels were produced by the classifier under test. Regenerate it."
        )

    settings = get_settings()
    print("=" * 62)
    print("  GRANDMATE EVALUATION")
    print("=" * 62)
    print(f"Dataset          : {len(dataset)} rows, oracle depth {oracle_depth}")
    print(f"Production depth : {settings.engine_depth}")
    print(f"Thresholds (cp)  : inaccuracy>={settings.inaccuracy_cp}, "
          f"mistake>={settings.mistake_cp}, blunder>={settings.blunder_cp}")
    print("\nDeterministic layer: production engine + classifier vs. oracle...")

    det = evaluate_detection(dataset, settings)

    print("\n" + "=" * 62)
    print("  DETECTION (vs. independent depth-%s oracle)" % oracle_depth)
    print("=" * 62)
    c = det["confusion"]
    print(f"n                 : {det['n']}   TP={c['tp']} FP={c['fp']} FN={c['fn']} TN={c['tn']}")
    print(f"Precision         : {fmt(det['precision'])}")
    print(f"Recall            : {fmt(det['recall'])}")
    print(f"Detection F1      : {fmt(det['detection_f1'])}   (target >= 0.90)")
    print(f"Severity Accuracy : {fmt(det['severity_accuracy'])}   (target >= 0.85)")
    print("\nAgreement by slice:")
    for key in ("expected_label", "phase", "side_to_move", "nature", "edge"):
        sl = slice_report(det["rows"], key)
        if sl:
            print(f"  {key:16s}: {sl}")

    report = {
        "meta": {
            "oracle_depth": oracle_depth,
            "production_depth": settings.engine_depth,
            "dataset_n": det["n"],
            "thresholds_cp": {"inaccuracy": settings.inaccuracy_cp,
                              "mistake": settings.mistake_cp,
                              "blunder": settings.blunder_cp},
        },
        "detection_f1": det["detection_f1"],
        "severity_accuracy": det["severity_accuracy"],
        "precision": det["precision"],
        "recall": det["recall"],
        "confusion": det["confusion"],
        "illegal_move_rate": None,
        "ragas_faithfulness": None,
        "coaching_quality": None,
        "judged_layer": "not run (pass --llm to measure)",
    }

    if args.llm:
        print("\n" + "=" * 62)
        print("  JUDGED LAYER (paid LLM calls)")
        print("=" * 62)
        judged = evaluate_judged(dataset, args.sample)
        report.update({
            "illegal_move_rate": judged["illegal_move_rate"],
            "ragas_faithfulness": judged["ragas_faithfulness"],
            "coaching_quality": judged["coaching_quality"],
            "judged_layer": judged,
        })
        print(f"\nIllegal / Hallucinated Rate : {fmt(judged['illegal_move_rate'], '.4%')} "
              f"(n={judged['moves_checked']} moves)")
        print(f"RAGAS Faithfulness          : {fmt(judged['ragas_faithfulness'])} "
              f"(n={judged['faithfulness_n']})   (target >= 0.85)")
        print(f"Coaching Quality            : {fmt(judged['coaching_quality'], '.2f')}/5 "
              f"(n={judged['coaching_n']})   (target >= 4.0)")
        if judged["judge_failures"] or judged["pipeline_failures"] or judged["rows_without_rag_context"]:
            print(f"\nNOT-MEASURED accounting: judge_failures={judged['judge_failures']}, "
                  f"pipeline_failures={judged['pipeline_failures']}, "
                  f"rows_without_rag_context={judged['rows_without_rag_context']}")

    print("\n" + "=" * 62)
    if args.no_save:
        print("--no-save: report.json left untouched.")
    else:
        report_file = ROOT / "evals" / "report.json"
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved JSON report to: {report_file}")


if __name__ == "__main__":
    main()
