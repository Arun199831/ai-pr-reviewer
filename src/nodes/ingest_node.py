import os
import base64
import requests
from src.state import PRReviewState


def get_relevant_lines(
    file_content: str,
    changed_lines: list[int],
    context: int = 50
) -> str:
    if not file_content or not changed_lines:
        return ""

    lines = file_content.split("\n")

    ranges = []
    for line_no in changed_lines:
        center = line_no - 1
        start = max(0, center - context)
        end = min(len(lines), center + context + 1)
        ranges.append((start, end))

    ranges.sort()
    merged = [list(ranges[0])]
    for start, end in ranges[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    chunks = ["\n".join(lines[s:e]) for s, e in merged]
    return "\n\n---\n\n".join(chunks)


def parse_changed_lines(patch: str) -> list[int]:
    changed_lines = []
    current_line = 0

    for line in patch.split("\n"):
        if line.startswith("@@"):
            try:
                new_info = line.split("+")[1].split("@@")[0].strip()
                current_line = int(new_info.split(",")[0])
            except (IndexError, ValueError):
                continue
        elif line.startswith("+") and not line.startswith("+++"):
            changed_lines.append(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass
        else:
            current_line += 1

    return changed_lines


def cost_guard(lines_changed: int, token_limit: int = 40_000) -> str:
    estimated_tokens = lines_changed * 5
    if estimated_tokens > token_limit:
        return "too_large"
    return "proceed"


def ingest_node(state: PRReviewState) -> dict:
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    owner = state["owner"]
    repo = state["repo"]
    pull_number = state["pull_number"]
    base_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"

    # Job 1 — fetch PR metadata
    pr_response = requests.get(base_url, headers=headers)
    pr_data = pr_response.json()

    files_changed = pr_data.get("changed_files", 0)
    lines_added = pr_data.get("additions", 0)
    lines_deleted = pr_data.get("deletions", 0)
    lines_changed = lines_added + lines_deleted

    # Job 2 — cost guard before fetching file content
    if cost_guard(lines_changed) == "too_large":
        return {
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "file_extensions": [],
            "relevant_code": "",
            "task_type": "too_large",
            "findings": [],
            "total_tokens": 0,
            "total_cost": 0.0,
            "agent_costs": {}
        }

    # Job 3 — fetch files and extract relevant lines
    files_response = requests.get(
        f"{base_url}/files",
        headers=headers
    )
    files_data = files_response.json()

    file_extensions = list(set([
        "." + f["filename"].split(".")[-1]
        for f in files_data
        if "." in f["filename"]
    ]))

    sorted_files = sorted(
        files_data,
        key=lambda f: (
            f["filename"].endswith(".py"),
            f.get("deletions", 0)
        ),
        reverse=True
    )

    all_relevant_code = []
    tokens_used = 0
    token_budget = 30_000

    for file_info in sorted_files:
        filename = file_info["filename"]
        patch = file_info.get("patch", "")

        if not patch:
            continue

        changed_lines = parse_changed_lines(patch)

        content_url = (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/contents/{filename}"
        )
        content_response = requests.get(
            content_url,
            headers=headers
        )

        if content_response.status_code == 200:
            content_data = content_response.json()
            file_content = base64.b64decode(
                content_data["content"]
            ).decode("utf-8", errors="replace")
            relevant = get_relevant_lines(file_content, changed_lines)
        else:
            relevant = patch

        file_tokens = len(relevant) // 4
        if tokens_used + file_tokens > token_budget:
            all_relevant_code.append(
                f"\n# SKIPPED: {filename} (token budget reached)"
            )
            continue

        all_relevant_code.append(f"\n# File: {filename}\n{relevant}")
        tokens_used += file_tokens

    return {
        "files_changed": files_changed,
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "file_extensions": file_extensions,
        "relevant_code": "\n\n".join(all_relevant_code),
        "findings": [],
        "total_tokens": 0,
        "total_cost": 0.0,
        "agent_costs": {}
    }