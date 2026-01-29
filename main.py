import argparse
import os
import re
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
from git import Repo
from src.code_agent import run_code_agent
from src.github_utils import create_pr, get_installation_token, get_issue
from src.logger import setup_logger


def parse_issue_url(issue_url: str) -> tuple[str, str, int]:
    """Extract owner, repo, and issue number from GitHub issue URL."""
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
    if not match:
        raise ValueError(f"Invalid issue URL: {issue_url}")
    return match.group(1), match.group(2), int(match.group(3))


def get_unique_branch_name(local_repo: Repo, base_name: str, logger) -> str:
    """Find unique branch name by checking remote branches."""
    remote_branches = [ref.name for ref in local_repo.remote().refs]
    logger.debug(f"Found {len(remote_branches)} remote branches")

    if f"origin/{base_name}" not in remote_branches:
        return base_name

    attempt = 1
    while True:
        candidate = f"{base_name}_{attempt}"
        if f"origin/{candidate}" not in remote_branches:
            logger.debug(f"Found unique branch name: {candidate}")
            return candidate
        attempt += 1


def main():
    load_dotenv()
    logger = setup_logger()

    parser = argparse.ArgumentParser(description="tishcode - AI coding agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    fixissue_parser = subparsers.add_parser("fixissue", help="Process GitHub issue")
    fixissue_parser.add_argument("issue_url", help="GitHub issue URL")
    
    args = parser.parse_args()

    owner, repo, issue_number = parse_issue_url(args.issue_url)
    logger.info(f"Processing issue #{issue_number} in {owner}/{repo}")

    app_id = os.getenv("GITHUB_APP_ID")
    private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
    base_repos_path = os.getenv("REPOS_BASE_PATH", "/tmp/tishcode-repos")

    if not app_id or not private_key_path:
        raise ValueError(
            "GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH must be set in .env"
        )

    with open(private_key_path, "r") as f:
        private_key_pem = f.read()

    logger.info("Getting installation token")
    installation_token = get_installation_token(app_id, private_key_pem, owner, repo)
    logger.debug(f"Installation token obtained")

    logger.info("Fetching issue details")
    issue = get_issue(installation_token, owner, repo, issue_number)
    logger.debug(f"Issue title: {issue.title}")
    
    unique_id = str(uuid.uuid4())[:8]
    repo_path = Path(base_repos_path) / f"{owner}_{repo}_{issue_number}_{unique_id}"
    repo_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Using temporary directory: {repo_path}")

    try:
        logger.info(f"Cloning repository to {repo_path}")
        repo_url = (
            f"https://x-access-token:{installation_token}@github.com/{owner}/{repo}.git"
        )
        local_repo = Repo.clone_from(repo_url, repo_path)

        base_branch_name = f"tishcode/issue-{issue_number}"
        branch_name = get_unique_branch_name(local_repo, base_branch_name, logger)
        if branch_name != base_branch_name:
            logger.info(
                f"Branch {base_branch_name} already exists, using {branch_name}"
            )
        logger.info(f"Creating branch {branch_name}")
        local_repo.git.checkout("-b", branch_name)

        logger.info("Running code agent")
        pr_title, pr_body = run_code_agent(issue, repo_path)

        logger.info("Committing changes")
        local_repo.git.add(A=True)
        local_repo.index.commit(f"Agent: implement issue #{issue_number}")

        logger.info(f"Pushing to remote branch {branch_name}")
        local_repo.git.push("origin", branch_name)

        logger.info("Creating pull request")
        pr_url = create_pr(
            installation_token,
            owner,
            repo,
            head_branch=branch_name,
            base_branch="main",
            title=pr_title,
            body=pr_body,
        )

        logger.info(f"Pull request created: {pr_url}")
    finally:
        logger.debug(f"Cleaning up repository at {repo_path}")
        shutil.rmtree(repo_path, ignore_errors=True)


if __name__ == "__main__":
    main()
