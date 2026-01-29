from pathlib import Path

from github.Issue import Issue


def run_code_agent(issue: Issue, repo_path: Path) -> tuple[str, str]:
    """Run code agent to process issue (stub implementation)."""
    readme_path = repo_path / "README.md"

    if readme_path.exists():
        content = readme_path.read_text()
    else:
        content = ""

    content += (
        f"\n\n## Issue #{issue.number}: {issue.title}\n\nProcessed by tishcode agent.\n"
    )
    readme_path.write_text(content)

    pr_title = f"[Agent] Fix issue #{issue.number}"
    pr_body = f"Closes #{issue.number}\n\nAutomated changes by tishcode agent."

    return pr_title, pr_body
