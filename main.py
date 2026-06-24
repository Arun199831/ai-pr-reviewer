import hmac
import hashlib
import os
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from src.graph import run_pr_review

load_dotenv()

app = FastAPI(title="AI PR Reviewer")

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verifies GitHub webhook signature.
    GitHub signs every webhook with a secret you set.
    This prevents random people from calling your endpoint.
    """
    if not GITHUB_WEBHOOK_SECRET:
        return True
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/health")
async def health():
    """Health check — confirms the server is running."""
    return {"status": "ok"}


@app.post("/webhook")
async def github_webhook(request: Request):
    """
    Main endpoint. GitHub calls this when a PR is opened or updated.

    Flow:
    1. Verify the request is from GitHub
    2. Check it's a pull_request event
    3. Run the PR review graph
    4. Return 200 OK
    """
    # Step 1 — verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload = await request.body()

    if not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Step 2 — parse payload
    data = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "")

    # Only handle pull_request events
    if event_type != "pull_request":
        return {"status": "ignored", "reason": "not a pull_request event"}

    # Only handle opened or updated PRs
    action = data.get("action", "")
    if action not in ("opened", "synchronize"):
        return {"status": "ignored", "reason": f"action {action} not handled"}

    # Step 3 — run the review graph
    try:
        result = run_pr_review(data)
        return {
            "status": "completed",
            "verdict": result.get("verdict"),
            "findings_count": len(result.get("findings", [])),
            "cost": result.get("total_cost", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))