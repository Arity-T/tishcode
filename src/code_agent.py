import logging
from pathlib import Path

from github.Issue import Issue
from github.PullRequest import PullRequest


logger = logging.getLogger("tishcode")


def run_code_agent_fixissue(issue: Issue, repo_path: Path) -> tuple[str, str]:
    """Run code agent to process issue (stub implementation)."""
    logger.debug(f"Processing issue #{issue.number}: {issue.title}")
    
    readme_path = repo_path / "README.md"

    if readme_path.exists():
        content = readme_path.read_text()
    else:
        content = ""

    content += (
        f"\n\n## Issue #{issue.number}: {issue.title}\n\nProcessed by tishcode agent.\n"
    )
    readme_path.write_text(content)
    logger.debug("Updated README.md")

    pr_title = f"Fix issue {issue.title}"
    pr_body = f"Closes #{issue.number}\n\nAutomated changes by tishcode agent."

    return pr_title, pr_body


def run_code_agent_fixpr(issue: Issue, pull_request: PullRequest, repo_path: Path) -> str:
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
