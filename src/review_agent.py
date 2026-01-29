import logging

from github.Issue import Issue
from github.PullRequest import PullRequest
from github.WorkflowRun import WorkflowRun


logger = logging.getLogger("tishcode")


def run_review_agent(
    pull_request: PullRequest,
    issue: Issue,
    workflow_runs: list[WorkflowRun],
    failed_job_logs: dict[int, str],
) -> tuple[str, bool]:
    """Run review agent to analyze pull request (stub implementation)."""
    logger.debug(f"Reviewing PR #{pull_request.number}: {pull_request.title}")
    logger.debug(f"Related issue #{issue.number}: {issue.title}")
    
    comments = list(pull_request.get_issue_comments())
    logger.debug(f"Found {len(comments)} comments on PR")
    logger.debug(f"Found {len(workflow_runs)} workflow runs")
    logger.debug(f"Found {len(failed_job_logs)} failed jobs with logs")
    
    failed_runs = [run for run in workflow_runs if run.conclusion in ("failure", "timed_out")]
    
    review_comment = (
        f"Automated review by tishcode agent.\n\n"
        f"PR: {pull_request.title}\n"
        f"Related issue: #{issue.number} - {issue.title}\n"
        f"Comments reviewed: {len(comments)}\n"
        f"Workflow runs: {len(workflow_runs)}\n"
        f"Failed runs: {len(failed_runs)}\n"
        f"Failed jobs with logs: {len(failed_job_logs)}\n\n"
    )
    
    if failed_runs:
        review_comment += "## Failed Workflow Runs\n\n"
        for run in failed_runs:
            review_comment += f"- **{run.name}** ({run.conclusion})\n"
            jobs = list(run.jobs())
            failed_jobs = [job for job in jobs if job.conclusion in ("failure", "timed_out")]
            if failed_jobs:
                review_comment += f"  - Failed jobs: {', '.join([job.name for job in failed_jobs])}\n"
        review_comment += "\n"
    
    review_comment += "This is a stub implementation."
    approve = False
    
    return review_comment, approve
