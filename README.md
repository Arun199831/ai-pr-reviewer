# AI PR Reviewer

A production-grade multi-agent PR review system built with LangGraph.
Automatically reviews GitHub Pull Requests for security, code quality,
and performance issues.

## Architecture

GitHub Webhook → Ingest → Classifier → Agents (parallel) → Aggregator → Output

- Heuristic classifier routes PRs — zero LLM cost for obvious cases
- Security, Quality, Performance agents run in parallel (GPT-4o)
- Confidence threshold (0.7) + finding cap (7) prevents alert fatigue
- Cost guard rejects oversized PRs before any LLM call

## Tech Stack

- LangGraph — multi-agent orchestration with parallel fan-out
- FastAPI — GitHub webhook endpoint
- OpenAI GPT-4o / GPT-4o-mini — multi-model routing by complexity
- Docker — containerised deployment
- LangSmith — observability and tracing

## Setup

```bash
git clone https://github.com/Arun199831/ai-pr-reviewer
cd ai-pr-reviewer
cp .env.example .env
# Add your API keys to .env
docker-compose up
```

## Run Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Input scope | Relevant lines (~50) | Full file = $0.40/PR, relevant lines = $0.03/PR |
| Classification | Heuristic cascade | Free signals handle 70% of PRs, LLM for ambiguous 30% |
| Parallelism | Fan-out on complex PRs | Sequential = 90s, parallel = 30s |
| Precision vs recall | Optimise precision | False alarms kill developer trust |
| Finding limit | Max 7 per PR | Alert fatigue prevention |

## Interview Talking Points

- Multi-model routing: cheap model for simple tasks, GPT-4o for complex
- Parallel fan-out with LangGraph Send API + reducer for state merging
- Six failure modes handled: hallucination, timeout, oversized PR, trust collapse
- Eval-gated CI/CD: golden dataset + precision regression gate