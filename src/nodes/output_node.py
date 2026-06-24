import os
import requests
from src.state import PRReviewState, Finding

SEVERITY_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢"
}


def format_finding_comment(finding: Finding) -> str:
    emoji = SEVERITY_EMOJI.get(finding["severity"], "⚪")
    return (
        f"{emoji} **{finding['severity'].upper()}**\n\n"
        f"{finding['comment']}\n\n"
        f"**Suggested fix:** {finding['suggested_fix']}"
    )


def format_summary_comment(state: PRReviewState) -> str:
    verdict_text = {
        "approve": "✅ **APPROVED** — No significant issues found.",
        "comment": "💬 **REVIEW COMMENTS** — Some issues to consider.",
        "request_changes": "❌ **CHANGES REQUESTED** — High severity issues found."
    }.get(state.get("verdict", "comment"), "💬 Review completed.")

    cost = state.get("total_cost", 0)

    return (
        f"## 🤖 AI PR Review\n\n"
        f"{verdict_text}\n\n"
        f"**Summary:** {state.get('summary', '')}\n\n"
        f"*Review cost: ${cost:.4f}*"
    )


def output_node(state: PRReviewState) -> dict:
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    owner = state["owner"]
    repo = state["repo"]
    pull_number = state["pull_number"]
    base_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
    issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pull_number}/comments"

    # Scenario 1 — PR too large
    if state.get("task_type") == "too_large":
        requests.post(issue_url, headers=headers, json={
            "body": (
                f"⚠️ **PR Too Large for Automated Review**\n\n"
                f"This PR changed {state['files_changed']} files "
                f"({state['lines_added'] + state['lines_deleted']} lines).\n\n"
                f"**Recommendation:** Split this PR into smaller changes."
            )
        })
        return {}

    findings = state.get("findings", [])

    # Scenario 2 — No findings
    if not findings:
        requests.post(
            f"{base_url}/reviews",
            headers=headers,
            json={
                "body": format_summary_comment(state),
                "event": "APPROVE"
            }
        )
        return {}

    # Scenario 3 — Post inline comments
    comments = []
    for finding in findings:
        comments.append({
            "path": finding["file"],
            "line": finding["line"],
            "body": format_finding_comment(finding)
        })

    event_map = {
        "approve": "APPROVE",
        "comment": "COMMENT",
        "request_changes": "REQUEST_CHANGES"
    }
    github_event = event_map.get(state.get("verdict", "comment"), "COMMENT")

    requests.post(
        f"{base_url}/reviews",
        headers=headers,
        json={
            "body": format_summary_comment(state),
            "event": github_event,
            "comments": comments
        }
    )

    return {}