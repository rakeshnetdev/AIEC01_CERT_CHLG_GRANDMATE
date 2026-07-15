import json
import sys
import pytest
from pathlib import Path

# Add backend src folder to python path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from config.settings import get_settings
from coach.analysis.classify import calculate_cpl_and_label

def load_dataset():
    dataset_file = ROOT / "evals" / "synthetic_dataset.json"
    if not dataset_file.exists():
        pytest.skip("synthetic_dataset.json does not exist. Run generate_synthetic.py first.")
    with open(dataset_file, "r", encoding="utf-8") as f:
        return json.load(f)

def test_mistake_detection_f1():
    dataset = load_dataset()
    settings = get_settings()
    
    tp = 0
    fp = 0
    fn = 0
    tn = 0
    
    for item in dataset:
        best_uci = item["expected_best_uci"]
        played_uci = item["played_uci"]
        score_before = item["score_before"]
        score_after = item["score_after"]
        expected_label = item["expected_label"]
        
        # Run classification
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
            
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0
    
    print(f"\nMistake Detection Metrics:")
    print(f"TP: {tp}, FP: {fp}, FN: {fn}, TN: {tn}")
    print(f"Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}")
    
    assert f1 >= 0.90

def test_severity_accuracy():
    dataset = load_dataset()
    settings = get_settings()
    
    correct = 0
    total = len(dataset)
    
    for item in dataset:
        best_uci = item["expected_best_uci"]
        played_uci = item["played_uci"]
        score_before = item["score_before"]
        score_after = item["score_after"]
        expected_label = item["expected_label"]
        
        # Run classification
        _, predicted_label = calculate_cpl_and_label(
            best_uci=best_uci,
            played_uci=played_uci,
            score_before=score_before,
            score_after=score_after,
            settings=settings
        )
        
        if expected_label == predicted_label:
            correct += 1
            
    accuracy = correct / total if total > 0 else 1.0
    print(f"Severity Classification Accuracy: {accuracy:.4f} ({correct}/{total})")
    
    assert accuracy >= 0.85
