import os
import re
import argparse
from pathlib import Path
from git import Repo
from dotenv import load_dotenv

from src.github_utils import get_installation_token, get_issue, create_pr
from src.code_agent import run_code_agent


def parse_issue_url(issue_url: str) -> tuple[str, str, int]:
    """Extract owner, repo, and issue number from GitHub issue URL."""
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
    if not match:
        raise ValueError(f"Invalid issue URL: {issue_url}")
    return match.group(1), match.group(2), int(match.group(3))


def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Process GitHub issue with tishcode agent")
    parser.add_argument("--issue-url", required=True, help="GitHub issue URL")
    args = parser.parse_args()
    
    owner, repo, issue_number = parse_issue_url(args.issue_url)
    
    app_id = os.getenv("GITHUB_APP_ID")
    private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
    base_repos_path = os.getenv("REPOS_BASE_PATH", "/tmp/tishcode-repos")
    
    if not app_id or not private_key_path:
        raise ValueError("GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH must be set in .env")
    
    with open(private_key_path, "r") as f:
        private_key_pem = f.read()
    
    installation_token = get_installation_token(app_id, private_key_pem, owner, repo)
    
    issue = get_issue(installation_token, owner, repo, issue_number)
    
    repo_path = Path(base_repos_path) / f"{owner}_{repo}"
    repo_path.mkdir(parents=True, exist_ok=True)
    
    repo_url = f"https://x-access-token:{installation_token}@github.com/{owner}/{repo}.git"
    local_repo = Repo.clone_from(repo_url, repo_path)
    
    branch_name = f"tishcode/issue-{issue_number}"
    local_repo.git.checkout("-b", branch_name)
    
    pr_title, pr_body = run_code_agent(issue, repo_path)
    
    local_repo.git.add(A=True)
    local_repo.index.commit(f"Agent: implement issue #{issue_number}")
    local_repo.git.push("origin", branch_name)
    
    pr_url = create_pr(
        installation_token,
        owner,
        repo,
        head_branch=branch_name,
        base_branch="main",
        title=pr_title,
        body=pr_body,
    )
    
    print(f"Created PR: {pr_url}")


if __name__ == "__main__":
    main()
