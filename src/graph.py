import os
from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from src.state import PRReviewState
from src.nodes.ingest_node import ingest_node
from src.nodes.classifier_node import (
    heuristic_classifier_node,
    llm_classifier_node,
    route_after_heuristic,
    route_after_llm_classifier
)
from src.agents.review_agents import (
    security_agent_node,
    code_quality_agent_node,
    performance_agent_node
)
from src.nodes.aggregator_node import aggregator_node
from src.nodes.output_node import output_node


def fan_out_to_agents(state: PRReviewState):
    """
    Send API — fires all three agents simultaneously.
    LangGraph waits for all three to finish before
    moving to aggregator. Reducer merges their findings.
    """
    return [
        Send("security_agent", state),
        Send("quality_agent", state),
        Send("performance_agent", state)
    ]


def build_graph():
    graph = StateGraph(PRReviewState)

    # Register all nodes
    graph.add_node("ingest_node", ingest_node)
    graph.add_node("heuristic_classifier_node", heuristic_classifier_node)
    graph.add_node("llm_classifier_node", llm_classifier_node)
    graph.add_node("security_agent", security_agent_node)
    graph.add_node("quality_agent", code_quality_agent_node)
    graph.add_node("performance_agent", performance_agent_node)
    graph.add_node("aggregator_node", aggregator_node)
    graph.add_node("output_node", output_node)

    # Entry point
    graph.set_entry_point("ingest_node")

    # Unconditional edges
    graph.add_edge("ingest_node", "heuristic_classifier_node")
    graph.add_edge("llm_classifier_node", "heuristic_classifier_node")

    # Conditional edges after heuristic classifier
    graph.add_conditional_edges(
        "heuristic_classifier_node",
        route_after_heuristic,
        {
            "quality_agent": "quality_agent",
            "review_agents": fan_out_to_agents,
            "llm_classifier_node": "llm_classifier_node",
            "output_node": "output_node"
        }
    )

    # All agents flow into aggregator
    graph.add_edge("security_agent", "aggregator_node")
    graph.add_edge("quality_agent", "aggregator_node")
    graph.add_edge("performance_agent", "aggregator_node")

    # Final flow
    graph.add_edge("aggregator_node", "output_node")
    graph.add_edge("output_node", END)

    return graph.compile()


def build_pr_state(webhook_payload: dict) -> dict:
    pr = webhook_payload["pull_request"]
    repo = webhook_payload["repository"]

    return {
        "owner": repo["owner"]["login"],
        "repo": repo["name"],
        "pull_number": pr["number"],
        "title": pr["title"],
        "description": pr["body"] or "",
        "files_changed": pr["changed_files"],
        "lines_added": pr["additions"],
        "lines_deleted": pr["deletions"],
        "file_extensions": [],
        "relevant_code": "",
        "task_type": "",
        "findings": [],
        "verdict": "",
        "summary": "",
        "total_tokens": 0,
        "total_cost": 0.0,
        "agent_costs": {},
        "trace_id": ""
    }


def run_pr_review(webhook_payload: dict) -> dict:
    graph = build_graph()
    initial_state = build_pr_state(webhook_payload)
    return graph.invoke(initial_state)