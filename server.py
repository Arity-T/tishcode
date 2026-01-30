"""FastAPI webhook server for tishcode."""

import hashlib
import hmac
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from src.handlers import handle_fixissue
from src.logger import setup_logger

load_dotenv()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
if not WEBHOOK_SECRET:
    raise RuntimeError("Missing GITHUB_WEBHOOK_SECRET in .env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = setup_logger()
    logger.info("tishcode webhook server started")
    yield
    logger.info("tishcode webhook server stopped")


app = FastAPI(title="tishcode webhook server", lifespan=lifespan)


def verify_github_signature(body: bytes, sig_header: str | None) -> None:
    """Verify GitHub webhook signature."""
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing X-Hub-Signature-256")

    try:
        algo, their_sig = sig_header.split("=", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad X-Hub-Signature-256 format")

    if algo != "sha256":
        raise HTTPException(status_code=400, detail="Unsupported signature algorithm")

    mac = hmac.new(WEBHOOK_SECRET.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()

    if not hmac.compare_digest(expected, their_sig):
        raise HTTPException(status_code=401, detail="Invalid signature")


def process_issue_opened(issue_url: str) -> None:
    """Background task to process opened issue."""
    logger = setup_logger()
    logger.info(f"[webhook] Processing new issue: {issue_url}")
    try:
        pr_url = handle_fixissue(issue_url)
        logger.info(f"[webhook] Created PR: {pr_url}")
    except Exception as e:
        logger.error(f"[webhook] Failed to process issue: {e}")


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events."""
    body = await request.body()
    verify_github_signature(body, request.headers.get("X-Hub-Signature-256"))

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()
    action = payload.get("action")

    logger = setup_logger()

    # GitHub ping event for webhook setup
    if event == "ping":
        logger.info("[webhook] Ping received")
        return {"ok": True, "message": "pong"}

    # Handle issue opened
    if event == "issues" and action == "opened":
        issue_url = payload.get("issue", {}).get("html_url")
        if issue_url:
            logger.info(f"[webhook] Issue opened: {issue_url}")
            background_tasks.add_task(process_issue_opened, issue_url)
            return {"ok": True, "message": "Processing issue in background"}
        return {"ok": False, "message": "No issue URL in payload"}

    # Ignore other events for now
    logger.debug(f"[webhook] Ignored event: {event} action: {action}")
    return {"ok": True, "message": f"Event {event}/{action} ignored"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
