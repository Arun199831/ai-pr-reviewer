import os
from openai import OpenAI
from src.state import PRReviewState

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def classify_pr(pr_data: dict) -> str:
    files_changed = pr_data["files_changed"]
    lines_changed = (
        pr_data["lines_added"] +
        pr_data["lines_deleted"]
    )
    extensions = pr_data["file_extensions"]

    if files_changed == 0 or lines_changed == 0 or not extensions:
        return "ambiguous"

    if (
        files_changed <= 2
        and lines_changed < 20
        and all(ext in [".md", ".txt"] for ext in extensions)
    ):
        return "simple"

    if (
        files_changed > 5
        or lines_changed > 200
        or (
            any(ext in [".py", ".java"] for ext in extensions)
            and lines_changed > 50
        )
    ):
        return "complex"

    return "ambiguous"


def heuristic_classifier_node(state: PRReviewState) -> dict:
    task_type = classify_pr({
        "files_changed": state["files_changed"],
        "lines_added": state["lines_added"],
        "lines_deleted": state["lines_deleted"],
        "file_extensions": state["file_extensions"]
    })
    return {"task_type": task_type}


def llm_classifier_node(state: PRReviewState) -> dict:
    pr_summary = f"""
    PR Title: {state['title']}
    Files changed: {state['files_changed']}
    Lines added: {state['lines_added']}
    Lines deleted: {state['lines_deleted']}
    File types: {', '.join(state['file_extensions'])}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=10,
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify this PR as simple or complex. "
                    "Simple: docs, config, small fixes under 50 lines. "
                    "Complex: logic changes, refactoring, new features. "
                    "Reply with exactly one word: simple or complex."
                )
            },
            {"role": "user", "content": pr_summary}
        ]
    )

    result = response.choices[0].message.content.strip().lower()
    task_type = "complex" if "complex" in result else "simple"

    tokens_used = response.usage.total_tokens
    cost = tokens_used * 0.0000001

    return {
        "task_type": task_type,
        "total_tokens": state.get("total_tokens", 0) + tokens_used,
        "total_cost": state.get("total_cost", 0.0) + cost,
        "agent_costs": {
            **state.get("agent_costs", {}),
            "llm_classifier": cost
        }
    }


def route_after_heuristic(state: PRReviewState) -> str:
    task_type = state["task_type"]

    if task_type == "simple":
        return "quality_agent"
    elif task_type == "complex":
        return "review_agents"
    elif task_type == "ambiguous":
        return "llm_classifier_node"
    else:
        return "output_node"


def route_after_llm_classifier(state: PRReviewState) -> str:
    if state["task_type"] == "simple":
        return "quality_agent"
    return "review_agents"