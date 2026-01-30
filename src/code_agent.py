import json
import logging
import os
from pathlib import Path
from textwrap import dedent

from agno.agent import Agent
from agno.tools.file import FileTools
from github.Issue import Issue
from github.PullRequest import PullRequest
from pydantic import BaseModel, Field

from .agent_utils import create_openai_model, get_pr_changes

logger = logging.getLogger("tishcode")


class PRResult(BaseModel):
    """Structured output for pull request creation."""

    pr_title: str = Field(description="Short, clear PR title describing the fix")
    pr_body: str = Field(description="Detailed PR description with changes summary")


def run_code_agent_fixissue(issue: Issue, repo_path: Path) -> tuple[str, str]:
    """Run code agent to fix issue and return PR title and body."""
    logger.info(f"Starting agent to fix issue #{issue.number}: {issue.title}")

    agent = Agent(
        name="TishCodeAgent",
        model=create_openai_model(),
        tools=[FileTools(base_dir=repo_path, enable_delete_file=True)],
        output_schema=PRResult,
        use_json_mode=True,
        instructions=dedent("""\
            You are a code fixing agent. Your task is to analyze codebases and fix reported issues.
            
            **Your Task:**
            1. Analyze the codebase using available file tools
            2. Identify what needs to be changed to fix the issue
            3. Make necessary code changes
            4. Return a PR title and PR body describing your changes
            
            **Guidelines:**
            - Make focused, minimal changes to fix the issue
            - Follow existing code style and conventions
            - Ensure your changes are clear and well-documented
            - The PR body should explain what was changed and why
            - Write the PR title and PR body in the same language as the issue (title and body)
            - You can edit .github/workflows files if necessary to fix the issue
        """),
        tool_call_limit=int(os.getenv("TC_AGENT_TOOL_CALL_LIMIT")),
    )

    user_message = dedent(f"""\
        Fix the following issue:
        
        **Issue title: {issue.title}**

        **Issue body:**

        {issue.body or "No description provided."}
    """)

    response = agent.run(user_message, stream=False)

    result: PRResult = response.content
    logger.info(f"Agent completed. PR title: {result.pr_title}")

    return result.pr_title, result.pr_body


def run_code_agent_fixpr(
    issue: Issue, pull_request: PullRequest, repo_path: Path
) -> str:
    """Run code agent to fix PR based on review feedback."""
    logger.info(f"Starting agent to fix PR #{pull_request.number}")

    # Get the latest review
    reviews = list(pull_request.get_reviews())
    if not reviews:
        logger.warning("No reviews found for this PR")
        latest_review_body = "No review comments available"
    else:
        latest_review = reviews[-1]
        latest_review_body = latest_review.body or "No review body provided"
        logger.debug(
            f"Latest review by {latest_review.user.login}: {latest_review.state}"
        )

    # Get code changes
    logger.debug("Fetching file changes from PR")
    changes = get_pr_changes(pull_request)

    agent = Agent(
        name="TishCodeFixPRAgent",
        model=create_openai_model(),
        tools=[FileTools(base_dir=repo_path, enable_delete_file=True)],
        instructions=dedent("""\
            You are a code fixing agent. Your task is to fix pull requests based on review feedback.
            
            **Your Task:**
            1. Read and understand the review feedback
            2. Analyze the codebase using available file tools
            3. Identify what needs to be changed based on the review
            4. Make necessary code changes to address all feedback
            5. Return a brief comment describing what was fixed
            
            **Guidelines:**
            - Address all issues mentioned in the review
            - Review feedback may contain errors or unreasonable suggestions - verify that changes make sense
            - If the review suggests something incorrect, explain why and provide a better solution
            - Follow existing code style and conventions
            - Make focused, clear changes
            - Ensure your changes are well-documented
            - Write the comment in the same language as the review
            - You can edit .github/workflows files if necessary to fix the issues
        """),
        tool_call_limit=int(os.getenv("TC_AGENT_TOOL_CALL_LIMIT")),
    )

    user_message = dedent(f"""\
        Fix the following pull request based on review feedback:
        
        **PR #{pull_request.number}: {pull_request.title}**
        
        **Related Issue #{issue.number}: {issue.title}**
        {issue.body or "No description provided."}
        
        **Current Code Changes in PR:**
        ```json
        {json.dumps(changes, indent=2, ensure_ascii=False)}
        ```
        
        **Latest Review Feedback:**
        {latest_review_body}
        
        Please analyze the current changes, understand the feedback, and apply necessary fixes.
    """)

    logger.debug("Running fix PR agent")
    response = agent.run(user_message, stream=False)

    comment = response.content
    logger.info("Agent completed fixes")

    return comment
