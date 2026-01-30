import logging
import os
from pathlib import Path
from textwrap import dedent

from agno.agent import Agent
from agno.tools.file import FileTools
from github.Issue import Issue
from github.PullRequest import PullRequest
from pydantic import BaseModel, Field

from .agent_utils import create_openai_model

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
        tools=[FileTools(base_dir=repo_path)],
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
    """Run code agent to fix pull request (stub implementation)."""
    logger.debug(f"Fixing PR #{pull_request.number}: {pull_request.title}")
    logger.debug(f"Related issue #{issue.number}: {issue.title}")

    readme_path = repo_path / "README.md"

    if readme_path.exists():
        content = readme_path.read_text()
    else:
        content = ""

    content += (
        f"\n\n## PR #{pull_request.number} Fixed\n\n"
        f"Related issue: #{issue.number} - {issue.title}\n"
        f"Fixed by tishcode agent.\n"
    )
    readme_path.write_text(content)
    logger.debug("Updated README.md")

    comment = (
        f"✅ Исправления внесены!\n\n"
        f"Изменения были применены в соответствии с issue #{issue.number}.\n"
        f"Пожалуйста, проверьте обновления."
    )

    return comment
