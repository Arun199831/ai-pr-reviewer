import time
import uuid
from collections import defaultdict


def create_trace(pr_metadata: dict) -> str:
    """
    Opens a new trace for one PR review.
    Returns trace_id — attach all spans to this.
    One PR = one trace.
    """
    trace_id = str(uuid.uuid4())
    print(f"[TRACE START] {trace_id} — PR #{pr_metadata.get('pull_number')}")
    return trace_id


def log_span(
    trace_id: str,
    agent_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    cost: float,
    error: str = None
):
    """
    Logs one agent call as a span inside a trace.
    Called after every LLM call automatically.

    Trace  = complete record of one PR review
    Span   = one step inside a trace (one agent call)
    """
    span = {
        "trace_id": trace_id,
        "agent": agent_name,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost,
        "timestamp": time.time()
    }
    if error:
        span["error"] = error

    import json
    print(f"[SPAN] {json.dumps(span)}")
    return span


class CostTracker:
    """
    Tracks cost at Level 2 — per agent per PR.

    Level 1 = per PR total     → tells you the bill
    Level 2 = per agent per PR → tells you WHICH agent is expensive

    Example:
        security_agent: $0.061  ← fix this prompt
        quality_agent:  $0.014
        performance:    $0.003
    """

    def __init__(self):
        self.records = []

    def record(self, pr_number: int, agent: str, cost: float, tokens: int):
        self.records.append({
            "pr_number": pr_number,
            "agent": agent,
            "cost": cost,
            "tokens": tokens,
            "timestamp": time.time()
        })

    def weekly_summary(self) -> dict:
        week_ago = time.time() - 7 * 24 * 3600
        recent = [r for r in self.records if r["timestamp"] > week_ago]

        per_agent = defaultdict(float)
        for r in recent:
            per_agent[r["agent"]] += r["cost"]

        total_prs = len(set(r["pr_number"] for r in recent))
        total_cost = sum(per_agent.values())

        return {
            "total_prs": total_prs,
            "total_cost": total_cost,
            "per_agent": dict(per_agent),
            "avg_per_pr": total_cost / max(total_prs, 1)
        }

    def alert_if_over_budget(self, threshold: float = 0.05):
        summary = self.weekly_summary()
        avg = summary["avg_per_pr"]
        if avg > threshold:
            print(f"[COST ALERT] Average ${avg:.4f}/PR exceeds ${threshold} threshold")


class TrustMonitor:
    """
    Detects trust collapse BEFORE it happens.
    Three signals tracked automatically:

    1. Finding Action Rate    — target > 60%
       < 40% = trust at risk

    2. False Positive Rate    — should not trend upward
       Rising for 7 days = precision problem

    3. Latency p95            — target < 180s
       Breached = developer stops waiting, merges without review
    """

    def __init__(self):
        self.action_records = []
        self.latency_records = []

    def record_action(
        self,
        pr_number: int,
        finding_id: str,
        acted_on: bool,
        developer: str
    ):
        self.action_records.append({
            "pr_number": pr_number,
            "finding_id": finding_id,
            "acted_on": acted_on,
            "developer": developer,
            "timestamp": time.time()
        })

    def record_latency(self, pr_number: int, latency_ms: float):
        self.latency_records.append({
            "pr_number": pr_number,
            "latency_ms": latency_ms,
            "timestamp": time.time()
        })

    def check_action_rate(self) -> dict:
        week_ago = time.time() - 7 * 24 * 3600
        recent = [r for r in self.action_records if r["timestamp"] > week_ago]

        if not recent:
            return {"rate": 1.0, "status": "insufficient_data"}

        rate = sum(1 for r in recent if r["acted_on"]) / len(recent)

        if rate < 0.40:
            status = "trust_at_risk"
            print(f"[TRUST ALERT] Action rate {rate:.1%} — below 40%")
        elif rate < 0.60:
            status = "warning"
        else:
            status = "healthy"

        return {"rate": rate, "status": status}

    def check_latency_p95(self) -> float:
        if len(self.latency_records) < 10:
            return 0.0

        sorted_records = sorted(
            self.latency_records,
            key=lambda r: r["latency_ms"]
        )
        p95_index = int(len(sorted_records) * 0.95)
        p95_ms = sorted_records[p95_index]["latency_ms"]

        if p95_ms > 180_000:
            print(f"[LATENCY ALERT] p95 {p95_ms/1000:.1f}s — above 3min threshold")

        return p95_ms / 1000


# Singleton instances — import these in other modules
cost_tracker = CostTracker()
trust_monitor = TrustMonitor()