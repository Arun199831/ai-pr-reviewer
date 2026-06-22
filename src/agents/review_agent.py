import os
import json
import time
from openai import OpenAI
from src.state import PRReviewState, Finding

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

GPT4O_INPUT_COST = 0.000005
GPT4O_OUTPUT_COST = 0.000015


def _call_agent(
    agent_name: str,
    system_prompt: str,
    state: PRReviewState,
    model: str = "gpt-4o"
) -> dict:
    user_prompt = f"""
PR Title: {state['title']}
Description: {state['description']}

Code to review:
{state['relevant_code']}

Return a JSON array of findings. Each finding must have:
- file: string
- line: integer  
- severity: "high", "medium", or "low"
- comment: string (what the issue is)
- suggested_fix: string (how to fix it)
- confidence: float between 0.0 and 1.0
- evidence: string (quote the EXACT line from the code)

If no issues found, return empty array: []
Return ONLY the JSON array, nothing else.
"""

    max_retries = 3
    wait_time = 2

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            break
        except Exception as e:
            if attempt == max_retries - 1:
                return {
                    "findings": [],
                    "total_tokens": state.get("total_tokens", 0),
                    "total_cost": state.get("total_cost", 0.0),
                    "agent_costs": {
                        **state.get("agent_costs", {}),
                        agent_name: 0.0
                    }
                }
            time.sleep(wait_time)
            wait_time *= 2

    try:
        raw = response.choices[0].message.content
        raw_findings = json.loads(raw)
        if not isinstance(raw_findings, list):
            raw_findings = []
    except json.JSONDecodeError:
        raw_findings = []

    findings = []
    for f in raw_findings:
        try:
            findings.append(Finding(
                file=f.get("file", "unknown"),
                line=int(f.get("line", 0)),
                severity=f.get("severity", "low"),
                comment=f.get("comment", ""),
                suggested_fix=f.get("suggested_fix", ""),
                confidence=float(f.get("confidence", 0.5)),
                agent=agent_name
            ))
        except (ValueError, TypeError):
            continue

    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    cost = (input_tokens * GPT4O_INPUT_COST +
            output_tokens * GPT4O_OUTPUT_COST)

    return {
        "findings": findings,
        "total_tokens": state.get("total_tokens", 0) + response.usage.total_tokens,
        "total_cost": state.get("total_cost", 0.0) + cost,
        "agent_costs": {
            **state.get("agent_costs", {}),
            agent_name: cost
        }
    }


SECURITY_PROMPT = """You are a senior security engineer reviewing a pull request.
Focus ONLY on security vulnerabilities. Do not comment on style or performance.

Look for: SQL injection, XSS, hardcoded secrets, missing input validation,
insecure authentication, sensitive data exposure.

Only flag real issues with clear evidence.
If confidence is below 0.7, do not include the finding."""


QUALITY_PROMPT = """You are a senior software engineer reviewing a pull request.
Focus ONLY on code quality and maintainability. Not security or performance.

Look for: functions doing too many things, missing error handling,
code duplication, unclear naming, dead code, unnecessary complexity.

Only flag real maintainability issues.
If confidence is below 0.7, do not include the finding."""


PERFORMANCE_PROMPT = """You are a senior performance engineer reviewing a pull request.
Focus ONLY on performance and efficiency. Not security or code style.

Look for: N+1 queries, missing indexes, inefficient algorithms,
unnecessary network calls in loops, missing caching.

Only flag issues with measurable performance impact.
If confidence is below 0.7, do not include the finding."""


def security_agent_node(state: PRReviewState) -> dict:
    return _call_agent("security_agent", SECURITY_PROMPT, state, "gpt-4o")


def code_quality_agent_node(state: PRReviewState) -> dict:
    model = "gpt-4o" if state["task_type"] == "complex" else "gpt-4o-mini"
    return _call_agent("quality_agent", QUALITY_PROMPT, state, model)


def performance_agent_node(state: PRReviewState) -> dict:
    return _call_agent("performance_agent", PERFORMANCE_PROMPT, state, "gpt-4o")