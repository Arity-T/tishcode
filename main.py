import argparse
import os
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
from git import Repo
from src.code_agent import run_code_agent
from src.review_agent import run_review_agent
from src.github_utils import (
    create_pr,
    get_github_repo,
    get_installation_token,
    get_issue,
    get_pull_request,
    parse_issue_url,
    parse_pr_url,
    extract_issue_number_from_pr_title,
)
from src.logger import setup_logger


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
    
    review_parser = subparsers.add_parser("review", help="Review pull request")
    review_parser.add_argument("pr_url", help="GitHub pull request URL")
    
    args = parser.parse_args()
    
    if args.command == "fixissue":
        handle_fixissue(args.issue_url, logger)
    elif args.command == "review":
        handle_review(args.pr_url, logger)


def handle_fixissue(issue_url: str, logger):
    """Handle fixissue command."""
    owner, repo, issue_number = parse_issue_url(issue_url)
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

    logger.info("Getting GitHub repository")
    gh_repo = get_github_repo(installation_token, owner, repo)

    logger.info("Fetching issue details")
    issue = get_issue(gh_repo, issue_number)
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
        full_pr_title = f"[tishcode fix issue #{issue_number}] {pr_title}"
        pr_url = create_pr(
            gh_repo,
            head_branch=branch_name,
            base_branch="main",
            title=full_pr_title,
            body=pr_body,
        )

        logger.info(f"Pull request created: {pr_url}")
    finally:
        logger.debug(f"Cleaning up repository at {repo_path}")
        shutil.rmtree(repo_path, ignore_errors=True)


def handle_review(pr_url: str, logger):
    """Handle review command."""
    owner, repo, pr_number = parse_pr_url(pr_url)
    logger.info(f"Reviewing PR #{pr_number} in {owner}/{repo}")

    app_id = os.getenv("GITHUB_APP_ID")
    private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")

    if not app_id or not private_key_path:
        raise ValueError(
            "GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH must be set in .env"
        )

    with open(private_key_path, "r") as f:
        private_key_pem = f.read()

    logger.info("Getting installation token")
    installation_token = get_installation_token(app_id, private_key_pem, owner, repo)
    logger.debug("Installation token obtained")

    logger.info("Getting GitHub repository")
    gh_repo = get_github_repo(installation_token, owner, repo)

    logger.info("Fetching pull request details")
    pull_request = get_pull_request(gh_repo, pr_number)
    logger.debug(f"PR title: {pull_request.title}")

    issue_number = extract_issue_number_from_pr_title(pull_request.title)
    if not issue_number:
        raise ValueError(
            f"Could not extract issue number from PR title: {pull_request.title}"
        )
    logger.debug(f"Extracted issue number: {issue_number}")

    logger.info(f"Fetching related issue #{issue_number}")
    issue = get_issue(gh_repo, issue_number)
    logger.debug(f"Issue title: {issue.title}")

    logger.info("Running review agent")
    review_comment, approve = run_review_agent(pull_request, issue)

    logger.info("Posting review comment")
    pull_request.create_review(body=review_comment, event="COMMENT")

    logger.info(f"Review posted successfully (approve={approve})")


if __name__ == "__main__":
    main()
