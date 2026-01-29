import argparse
import os

from dotenv import load_dotenv
from src.code_agent import run_code_agent_fixissue, run_code_agent_fixpr
from src.git_utils import clone_temp_repo, get_unique_branch_name
from src.github_utils import (
    create_pr,
    extract_issue_number_from_pr_title,
    get_issue,
    get_pull_request,
    parse_issue_url,
    parse_pr_url,
    setup_github_access,
)
from src.logger import setup_logger
from src.review_agent import run_review_agent


def main():
    load_dotenv()
    logger = setup_logger()

    parser = argparse.ArgumentParser(description="tishcode - AI coding agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixissue_parser = subparsers.add_parser("fixissue", help="Process GitHub issue")
    fixissue_parser.add_argument("issue_url", help="GitHub issue URL")

    review_parser = subparsers.add_parser("review", help="Review pull request")
    review_parser.add_argument("pr_url", help="GitHub pull request URL")

    fixpr_parser = subparsers.add_parser("fixpr", help="Fix pull request")
    fixpr_parser.add_argument("pr_url", help="GitHub pull request URL")

    args = parser.parse_args()

    if args.command == "fixissue":
        handle_fixissue(args.issue_url, logger)
    elif args.command == "review":
        handle_review(args.pr_url, logger)
    elif args.command == "fixpr":
        handle_fixpr(args.pr_url, logger)


def handle_fixissue(issue_url: str, logger):
    """Handle fixissue command."""
    owner, repo, issue_number = parse_issue_url(issue_url)
    logger.info(f"Processing issue #{issue_number} in {owner}/{repo}")

    installation_token, gh_repo = setup_github_access(owner, repo, logger)

    logger.info("Fetching issue details")
    issue = get_issue(gh_repo, issue_number)
    logger.debug(f"Issue title: {issue.title}")

    with clone_temp_repo(owner, repo, installation_token) as (local_repo, repo_path):
        base_branch_name = f"tishcode/issue-{issue_number}"
        branch_name = get_unique_branch_name(local_repo, base_branch_name)
        if branch_name != base_branch_name:
            logger.info(
                f"Branch {base_branch_name} already exists, using {branch_name}"
            )
        logger.info(f"Creating branch {branch_name}")
        local_repo.git.checkout("-b", branch_name)

        logger.info("Running code agent")
        pr_title, pr_body = run_code_agent_fixissue(issue, repo_path)

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


def handle_review(pr_url: str, logger):
    """Handle review command."""
    owner, repo, pr_number = parse_pr_url(pr_url)
    logger.info(f"Reviewing PR #{pr_number} in {owner}/{repo}")

    _, gh_repo = setup_github_access(owner, repo, logger)

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


def handle_fixpr(pr_url: str, logger):
    """Handle fixpr command."""
    owner, repo, pr_number = parse_pr_url(pr_url)
    logger.info(f"Fixing PR #{pr_number} in {owner}/{repo}")

    installation_token, gh_repo = setup_github_access(owner, repo, logger)

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

    with clone_temp_repo(owner, repo, installation_token) as (local_repo, repo_path):
        branch_name = pull_request.head.ref
        logger.info(f"Checking out PR branch {branch_name}")
        local_repo.git.fetch("origin", branch_name)
        local_repo.git.checkout(branch_name)

        logger.info("Running code agent to fix PR")
        comment = run_code_agent_fixpr(issue, pull_request, repo_path)

        logger.info("Committing changes")
        local_repo.git.add(A=True)
        local_repo.index.commit(f"Agent: apply fixes for PR #{pr_number}")

        logger.info(f"Pushing to remote branch {branch_name}")
        local_repo.git.push("origin", branch_name)

        logger.info("Posting comment to PR")
        pull_request.create_issue_comment(body=comment)

        logger.info("PR fix completed successfully")


if __name__ == "__main__":
    main()
