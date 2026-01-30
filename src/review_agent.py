import json
import logging
import os
import re
from textwrap import dedent

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.WorkflowRun import WorkflowRun
from pydantic import BaseModel, Field

logger = logging.getLogger("tishcode")


class ReviewResult(BaseModel):
    """Structured output for PR review."""

    review_comment: str = Field(
        description="Review comment describing findings, errors, and suggestions"
    )
    approve: bool = Field(
        description="True if PR can be merged, False if issues need to be fixed"
    )


def preprocess_log_line(line: str, max_length: int = 1000) -> str:
    """Remove timestamp prefix and truncate long lines."""
    # Remove GitHub Actions timestamp (format: YYYY-MM-DDTHH:MM:SS.fffffffZ)
    line = re.sub(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*", "", line)

    # Truncate if too long
    if len(line) > max_length:
        line = line[:max_length] + "... [truncated]"

    return line


def extract_relevant_log_lines(log_text: str, context_lines: int = 50) -> str:
    """Extract relevant lines around error markers from logs."""
    if not log_text:
        return ""

    lines = log_text.split("\n")
    error_indices = []

    # Find all lines with error markers
    for i, line in enumerate(lines):
        if "##[error]" in line.lower() or "error:" in line.lower():
            error_indices.append(i)

    if not error_indices:
        # No errors found, return last N lines
        start_idx = max(0, len(lines) - context_lines)
        relevant_lines = lines[start_idx:]
    else:
        # Get context around first error
        first_error_idx = error_indices[0]
        start_idx = max(0, first_error_idx - context_lines)
        end_idx = min(len(lines), first_error_idx + 20)
        relevant_lines = lines[start_idx:end_idx]

    # Preprocess each line
    processed_lines = [preprocess_log_line(line) for line in relevant_lines]

    return "\n".join(processed_lines)


def run_review_agent(
    pull_request: PullRequest,
    issue: Issue,
    workflow_runs: list[WorkflowRun],
    failed_job_logs: dict[int, str],
) -> tuple[str, bool]:
    """Run review agent to analyze pull request and provide feedback."""
    logger.info(f"Starting review agent for PR #{pull_request.number}")

    # Get code changes
    logger.debug("Fetching file changes from PR")
    files = pull_request.get_files()
    changes = []
    for f in files:
        changes.append(
            {
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "patch": f.patch if f.patch else "Binary file or no diff available",
            }
        )

    # Prepare workflow runs summary
    logger.debug("Preparing workflow runs summary")
    workflows_summary = []
    for run in workflow_runs:
        jobs_info = []
        for job in run.jobs():
            jobs_info.append(
                {
                    "name": job.name,
                    "conclusion": job.conclusion,
                    "id": job.id,
                }
            )

        workflows_summary.append(
            {
                "name": run.name,
                "conclusion": run.conclusion,
                "jobs": jobs_info,
            }
        )

    # Prepare failed workflows with logs
    logger.debug("Preparing failed workflows data")
    failed_workflows = []
    for run in workflow_runs:
        if run.conclusion in ("failure", "timed_out"):
            failed_jobs_data = []
            for job in run.jobs():
                if job.conclusion in ("failure", "timed_out"):
                    log_text = failed_job_logs.get(job.id)
                    processed_log = (
                        extract_relevant_log_lines(log_text)
                        if log_text
                        else "No logs available"
                    )

                    failed_jobs_data.append(
                        {
                            "name": job.name,
                            "conclusion": job.conclusion,
                            "log": processed_log,
                        }
                    )

            if failed_jobs_data:
                failed_workflows.append(
                    {
                        "name": run.name,
                        "conclusion": run.conclusion,
                        "failed_jobs": failed_jobs_data,
                    }
                )

    # Create agent
    model_id = os.getenv("TC_OPENAI_MODEL")
    api_key = os.getenv("TC_OPENAI_API_KEY")
    base_url = os.getenv("TC_OPENAI_BASE_URL")

    if not model_id or not api_key or not base_url:
        raise ValueError("OpenAI environment variables are not set")

    logger.info(f"Creating review agent with model: {model_id}")

    agent = Agent(
        name="ReviewAgent",
        model=OpenAIChat(
            id=model_id,
            api_key=api_key,
            base_url=base_url,
        ),
        output_schema=ReviewResult,
        use_json_mode=True,
        instructions=dedent("""\
            You are a code review agent. Your task is to analyze pull requests and provide constructive feedback.
            
            **Your Task:**
            1. Review the code changes in the PR
            2. Check if changes match the issue requirements
            3. Analyze CI/CD workflow results
            4. Identify errors and their root causes
            5. Provide a review comment and approval decision
            
            **Guidelines:**
            - Be concise and constructive in your feedback
            - Focus on critical issues and errors
            - Explain what caused failures and suggest fixes
            - Approve (approve=true) only if all checks pass and changes are correct
            - Reject (approve=false) if there are failing tests or issues
            - Write the review comment in the same language as the issue
        """),
        tool_call_limit=int(os.getenv("TC_AGENT_TOOL_CALL_LIMIT", "30")),
        markdown=True,
    )

    # Prepare user message
    user_message = dedent(f"""\
        Review the following pull request:
        
        **PR Title: {pull_request.title}**
        
        **Related Issue Title: {issue.title}**
        {issue.body or "No description provided."}
        
        **Code Changes:**
        ```json
        {json.dumps(changes, indent=2, ensure_ascii=False)}
        ```
        
        **All Workflow Runs:**
        ```json
        {json.dumps(workflows_summary, indent=2, ensure_ascii=False)}
        ```
        
        **Failed Workflows with Logs:**
        ```json
        {json.dumps(failed_workflows, indent=2, ensure_ascii=False)}
        ```
        
        Analyze the changes and CI results, then provide your review.
    """)

    logger.debug("Running review agent")
    response = agent.run(user_message, stream=False)

    result: ReviewResult = response.content
    logger.info(f"Review completed. Approve: {result.approve}")

    return result.review_comment, result.approve
