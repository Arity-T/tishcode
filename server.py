"""FastAPI webhook server for tishcode."""

import hashlib
import hmac
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from src.db import (
    get_fix_attempts,
    increment_fix_attempts,
    is_pr_completed,
    mark_pr_completed,
)
from src.github_utils import (
    are_all_workflows_completed,
    get_pull_request,
    parse_pr_url,
    setup_github_access,
)
from src.handlers import handle_fixissue, handle_fixpr, handle_review
from src.logger import setup_logger

load_dotenv()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("Missing GITHUB_WEBHOOK_SECRET in .env")

_max_retries = os.getenv("TC_MAX_RETRIES")
if not _max_retries:
    raise RuntimeError("Missing TC_MAX_RETRIES in .env")
MAX_RETRIES = int(_max_retries)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger = setup_logger()
    logger.info("tishcode webhook server started")
    logger.info(f"Max fix retries: {MAX_RETRIES}")
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

    assert WEBHOOK_SECRET is not None
    mac = hmac.new(WEBHOOK_SECRET.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()

    if not hmac.compare_digest(expected, their_sig):
        raise HTTPException(status_code=401, detail="Invalid signature")


def process_issue_opened(issue_url: str) -> None:
    """Background task: issues/opened - handle_fixissue."""
    logger = setup_logger()
    logger.info(f"[webhook] Processing new issue: {issue_url}")
    try:
        pr_url = handle_fixissue(issue_url)
        logger.info(f"[webhook] Created PR: {pr_url}")
    except Exception as e:
        logger.error(f"[webhook] Failed to process issue: {e}")


def process_pr_review_submitted(pr_url: str) -> None:
    """Background task: pull_request_review/submitted - handle_fixpr."""
    logger = setup_logger()
    logger.info(f"[webhook] Processing PR review submitted: {pr_url}")

    try:
        owner, repo, pr_number = parse_pr_url(pr_url)

        # Check if PR processing is already completed
        if is_pr_completed(owner, repo, pr_number):
            logger.info(f"[webhook] PR {pr_url} already completed, skipping fixpr")
            return

        # Check retry limit
        attempts = get_fix_attempts(owner, repo, pr_number)
        if attempts >= MAX_RETRIES:
            logger.warning(
                f"[webhook] PR {pr_url} max retries ({MAX_RETRIES}) "
                "reached, skipping fixpr"
            )
            mark_pr_completed(owner, repo, pr_number)
            return

        # Run fixpr and increment counter
        logger.info(
            f"[webhook] Running fixpr for PR: {pr_url} (attempt {attempts + 1})"
        )
        increment_fix_attempts(owner, repo, pr_number)
        handle_fixpr(pr_url)
        logger.info(f"[webhook] Fixed PR: {pr_url}")

    except Exception as e:
        logger.error(f"[webhook] Failed to fix PR: {e}")


def process_check_suite_completed(pr_url: str) -> None:
    """Background task: check_suite/completed - handle_review."""
    logger = setup_logger()
    logger.info(f"[webhook] Processing check_suite completed for PR: {pr_url}")

    try:
        owner, repo, pr_number = parse_pr_url(pr_url)

        # Check if PR processing is already completed
        if is_pr_completed(owner, repo, pr_number):
            logger.info(f"[webhook] PR {pr_url} already completed, skipping review")
            return

        # Get PR to check all workflows status
        _, gh_repo = setup_github_access(owner, repo)
        pull_request = get_pull_request(gh_repo, pr_number)

        # Check if all workflows are completed
        if not are_all_workflows_completed(gh_repo, pull_request.head.sha):
            logger.info(
                f"[webhook] Not all workflows completed for PR {pr_url}, skipping"
            )
            return

        # Run review
        logger.info(f"[webhook] Running review for PR: {pr_url}")
        approved = handle_review(pr_url)

        if approved:
            logger.info(f"[webhook] PR {pr_url} approved, marking as completed")
            mark_pr_completed(owner, repo, pr_number)

    except Exception as e:
        logger.error(f"[webhook] Failed to review PR: {e}")


@app.post("/webhook")
async def github_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, str | bool]:
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

    # Handle issue opened - fixissue
    if event == "issues" and action == "opened":
        issue_url = payload.get("issue", {}).get("html_url")
        if issue_url:
            logger.info(f"[webhook] Issue opened: {issue_url}")
            background_tasks.add_task(process_issue_opened, issue_url)
            return {"ok": True, "message": "Processing issue in background"}
        return {"ok": False, "message": "No issue URL in payload"}

    # Handle pull request review submitted - fixpr
    if event == "pull_request_review" and action == "submitted":
        pr_url = payload.get("pull_request", {}).get("html_url")
        review_state = payload.get("review", {}).get("state")

        if pr_url:
            logger.info(
                f"[webhook] PR review submitted: {pr_url} (state: {review_state})"
            )
            background_tasks.add_task(process_pr_review_submitted, pr_url)
            return {"ok": True, "message": "Processing PR fix in background"}

        return {"ok": False, "message": "No PR URL in payload"}

    # Handle check_suite completed - review
    if event == "check_suite" and action == "completed":
        check_suite = payload.get("check_suite", {})
        pull_requests = check_suite.get("pull_requests", [])

        if not pull_requests:
            logger.debug("[webhook] check_suite has no PRs, ignoring")
            return {"ok": True, "message": "No PRs in check_suite"}

        # Process first PR (usually there's only one)
        pr_data = pull_requests[0]
        pr_number = pr_data.get("number")
        repo_data = payload.get("repository", {})
        pr_url = f"{repo_data.get('html_url')}/pull/{pr_number}"

        logger.info(f"[webhook] check_suite completed for PR: {pr_url}")
        background_tasks.add_task(process_check_suite_completed, pr_url)
        return {"ok": True, "message": "Processing review in background"}

    # Ignore other events
    logger.debug(f"[webhook] Ignored event: {event} action: {action}")
    return {"ok": True, "message": f"Event {event}/{action} ignored"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
