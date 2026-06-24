import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_golden_dataset(path: str = "evals/golden_dataset.json") -> list:
    with open(path) as f:
        return json.load(f)


def score_findings(actual: list, expected: list) -> tuple:
    """
    Returns (precision, recall, false_positive_rate).
    A finding matches if it points to the same file
    and within 3 lines of the expected line.
    """
    if not expected:
        if not actual:
            return 1.0, 1.0, 0.0
        return 0.0, 1.0, 1.0

    if not actual:
        return 1.0, 0.0, 0.0

    def is_match(act, exp):
        same_file = act.get("file", "") == exp.get("file", "")
        line_close = abs(act.get("line", 0) - exp.get("line", 0)) <= 3
        return same_file and line_close

    matched = set()
    true_positives = 0

    for act in actual:
        for i, exp in enumerate(expected):
            if i not in matched and is_match(act, exp):
                true_positives += 1
                matched.add(i)
                break

    false_positives = len(actual) - true_positives
    precision = true_positives / len(actual) if actual else 0.0
    recall = true_positives / len(expected) if expected else 0.0
    fpr = false_positives / len(actual) if actual else 0.0

    return precision, recall, fpr


def run_evals():
    """
    Runs eval suite against golden dataset.
    Prints precision, recall, FPR per example.
    Used as regression gate in CI.
    """
    dataset = load_golden_dataset()
    results = []

    print(f"\nRunning evals on {len(dataset)} golden examples...\n")

    for example in dataset:
        example_id = example["id"]
        expected_findings = example["expected_findings"]
        expected_verdict = example["expected_verdict"]

        # Note: in real CI this calls run_pr_review()
        # For now we print the expected values as a dry run
        print(f"Example {example_id}: {example['description']}")
        print(f"  Expected verdict:  {expected_verdict}")
        print(f"  Expected findings: {len(expected_findings)}")
        print()

        results.append({
            "id": example_id,
            "expected_verdict": expected_verdict,
            "expected_findings_count": len(expected_findings)
        })

    print(f"Eval suite complete. {len(results)} examples loaded.")
    print("Connect run_pr_review() to score against actual outputs.")
    return results


if __name__ == "__main__":
    run_evals()