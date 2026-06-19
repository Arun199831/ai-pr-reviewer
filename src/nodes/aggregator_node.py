import os
from openai import OpenAI
from src.state import PRReviewState, Finding

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CONFIDENCE_THRESHOLD = 0.7
FINDING_CAP = 7
SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


def aggregator_node(state: PRReviewState) -> dict:
    all_findings = state.get("findings", [])

    if not all_findings:
        return {
            "findings": [],
            "verdict": "approve",
            "summary": "No issues found. This PR looks good to merge."
        }

    # Mechanism 1 — confidence threshold
    # Filters hallucinations AND prevents alert fatigue
    confident_findings = [
        f for f in all_findings
        if f.get("confidence", 0) >= CONFIDENCE_THRESHOLD
    ]

    # Sort by severity — high first
    sorted_findings = sorted(
        confident_findings,
        key=lambda f: SEVERITY_ORDER.get(f["severity"], 0),
        reverse=True
    )

    # Mechanism 2 — finding cap
    # Never show more than 7 findings — alert fatigue prevention
    final_findings = sorted_findings[:FINDING_CAP]

    # Determine verdict
    has_high = any(f["severity"] == "high" for f in final_findings)
    has_medium = any(f["severity"] == "medium" for f in final_findings)

    if has_high:
        verdict = "request_changes"
    elif has_medium:
        verdict = "comment"
    else:
        verdict = "approve"

    high_count = sum(1 for f in final_findings if f["severity"] == "high")
    med_count = sum(1 for f in final_findings if f["severity"] == "medium")
    low_count = sum(1 for f in final_findings if f["severity"] == "low")

    summary = (
        f"Found {len(final_findings)} issue(s): "
        f"{high_count} high, {med_count} medium, {low_count} low severity."
    )

    return {
        "findings": final_findings,
        "verdict": verdict,
        "summary": summary
    }