"""Business logic handlers for tishcode commands."""

import logging

from src.code_agent import run_code_agent_fixissue, run_code_agent_fixpr
from src.git_utils import clone_temp_repo, get_unique_branch_name
from src.github_utils import (
    create_pr,
    extract_issue_number_from_pr_title,
    get_issue,
    get_pull_request,
    get_workflow_runs_and_logs,
    parse_issue_url,
    parse_pr_url,
    setup_github_access,
)
from src.review_agent import run_review_agent

logger = logging.getLogger("tishcode")


def add_agent_signature(text: str, action: str = "by") -> str:
    """Add agent signature footer to text."""
    return f"{text}\n\n---\n*🤖 Automated {action} tishcode agent*"


def handle_fixissue(issue_url: str) -> str:
    """Handle fixissue command. Returns created PR URL."""
    owner, repo, issue_number = parse_issue_url(issue_url)
    logger.info(f"Processing issue #{issue_number} in {owner}/{repo}")

    installation_token, gh_repo = setup_github_access(owner, repo)

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
        pr_body = f"{pr_body}\n\nCloses #{issue_number}"
        pr_body = add_agent_signature(pr_body)
        pr_url = create_pr(
            gh_repo,
            head_branch=branch_name,
            base_branch="main",
            title=full_pr_title,
            body=pr_body,
        )

        logger.info(f"Pull request created: {pr_url}")
        return pr_url


def handle_review(pr_url: str) -> bool:
    """Handle review command. Returns True if approved, False otherwise."""
    owner, repo, pr_number = parse_pr_url(pr_url)
    logger.info(f"Reviewing PR #{pr_number} in {owner}/{repo}")

    _, gh_repo = setup_github_access(owner, repo)

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

    logger.info("Getting workflow run results")
    workflow_runs, failed_job_logs = get_workflow_runs_and_logs(gh_repo, pull_request)

    logger.info("Running review agent")
    review_comment, approve = run_review_agent(
        pull_request, issue, workflow_runs, failed_job_logs
    )

    # Add approval status header
    status_icon = "✅" if approve else "❌"
    status_text = (
        "APPROVED - Ready to merge"
        if approve
        else "CHANGES REQUESTED - Issues need to be fixed"
    )

    formatted_comment = f"## {status_icon} Code Review Result: {status_text}\n\n"

    # Add failed workflows summary if any
    failed_runs = [
        run for run in workflow_runs if run.conclusion in ("failure", "timed_out")
    ]
    if failed_runs:
        formatted_comment += "### ⚠️ Failed Workflows\n\n"
        for run in failed_runs:
            formatted_comment += f"**{run.name}** ({run.conclusion})\n"
            jobs = list(run.jobs())
            failed_jobs = [
                job for job in jobs if job.conclusion in ("failure", "timed_out")
            ]
            if failed_jobs:
                formatted_comment += (
                    "  - Failed jobs: "
                    + ", ".join([f"`{job.name}`" for job in failed_jobs])
                    + "\n"
                )
        formatted_comment += "\n---\n\n"

    # Add agent's review comment
    formatted_comment += review_comment

    # Add footer signature
    formatted_comment = add_agent_signature(formatted_comment, "review by")

    logger.info("Posting review comment")
    pull_request.create_review(body=formatted_comment, event="COMMENT")

    logger.info(f"Review posted successfully (approve={approve})")
    return approve


def handle_fixpr(pr_url: str) -> None:
    """Handle fixpr command."""
    owner, repo, pr_number = parse_pr_url(pr_url)
    logger.info(f"Fixing PR #{pr_number} in {owner}/{repo}")

    installation_token, gh_repo = setup_github_access(owner, repo)

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
        comment = add_agent_signature(comment)
        pull_request.create_issue_comment(body=comment)

        logger.info("PR fix completed successfully")
