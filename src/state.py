from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class Finding(TypedDict):
    file: str
    line: int
    severity: str
    comment: str
    suggested_fix: str
    confidence: float
    agent: str
    
    
class PRReviewState(TypedDict):
    # PR identifiers
    owner: str
    repo: str
    pull_number: int
    title: str
    description: str

    # Classification inputs
    files_changed: int
    lines_added: int
    lines_deleted: int
    file_extensions: list[str]

    # Code content
    relevant_code: str

    # Classification output
    task_type: str

    # Findings — reducer merges parallel writes
    findings: Annotated[list[Finding], add]

    # Final output
    verdict: str
    summary: str

    # LLMOps tracking
    total_tokens: int
    total_cost: float
    agent_costs: dict
    trace_id: str