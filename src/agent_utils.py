import logging
import os

from github.PullRequest import PullRequest
from langchain_openai import ChatOpenAI

logger = logging.getLogger("tishcode")


def get_pr_changes(pull_request: PullRequest) -> list[dict[str, str | int]]:
    """Extract code changes from pull request in structured format."""
    files = pull_request.get_files()
    changes: list[dict[str, str | int]] = []
    for f in files:
        changes.append({
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "patch": f.patch if f.patch else "Binary file or no diff available",
        })
    return changes


def create_chat_model() -> ChatOpenAI:
    """Create LangChain ChatOpenAI model with validation of environment variables."""
    model_id = os.getenv("TC_OPENAI_MODEL")
    api_key = os.getenv("TC_OPENAI_API_KEY")
    base_url = os.getenv("TC_OPENAI_BASE_URL")

    if not model_id:
        raise ValueError("TC_OPENAI_MODEL environment variable is not set")
    if not api_key:
        raise ValueError("TC_OPENAI_API_KEY environment variable is not set")
    if not base_url:
        raise ValueError("TC_OPENAI_BASE_URL environment variable is not set")

    logger.info(f"Using model: {model_id}, base_url: {base_url}")

    return ChatOpenAI(
        model=model_id,
        api_key=api_key,
        base_url=base_url,
    )
