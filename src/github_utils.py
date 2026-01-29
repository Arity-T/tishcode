import time
import logging
import re

import jwt
import requests
from github import Github
from github.Issue import Issue
from github.Repository import Repository
from github.PullRequest import PullRequest

GITHUB_API = "https://api.github.com"
logger = logging.getLogger("tishcode")


def parse_issue_url(issue_url: str) -> tuple[str, str, int]:
    """Extract owner, repo, and issue number from GitHub issue URL."""
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
    if not match:
        raise ValueError(f"Invalid issue URL: {issue_url}")
    return match.group(1), match.group(2), int(match.group(3))


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Extract owner, repo, and PR number from GitHub pull request URL."""
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        raise ValueError(f"Invalid pull request URL: {pr_url}")
    return match.group(1), match.group(2), int(match.group(3))


def extract_issue_number_from_pr_title(pr_title: str) -> int | None:
    """Extract issue number from PR title with format '[tishcode fix issue #123]'."""
    match = re.search(r"\[tishcode fix issue #(\d+)\]", pr_title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def make_app_jwt(app_id: str, private_key_pem: str) -> str:
    """Generate JWT token for GitHub App authentication."""
    now = int(time.time())
    payload = {"iat": now - 30, "exp": now + 9 * 60, "iss": app_id}
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def get_installation_id(owner: str, repo: str, app_jwt: str) -> int:
    """Get installation ID for a repository."""
    r = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/installation",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def create_installation_token(installation_id: int, app_jwt: str) -> str:
    """Create installation token for repository access."""
    r = requests.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["token"]


def get_installation_token(
    app_id: str, private_key_pem: str, owner: str, repo: str
) -> str:
    """Get installation token for repository."""
    logger.debug(f"Creating JWT for app {app_id}")
    app_jwt = make_app_jwt(app_id, private_key_pem)
    
    logger.debug(f"Getting installation ID for {owner}/{repo}")
    inst_id = get_installation_id(owner, repo, app_jwt)
    logger.debug(f"Installation ID: {inst_id}")
    
    return create_installation_token(inst_id, app_jwt)


def get_github_repo(installation_token: str, owner: str, repo: str) -> Repository:
    """Get GitHub repository object."""
    gh = Github(installation_token)
    return gh.get_repo(f"{owner}/{repo}")


def get_issue(gh_repo: Repository, issue_number: int) -> Issue:
    """Fetch issue object from GitHub repository."""
    return gh_repo.get_issue(number=issue_number)


def get_pull_request(gh_repo: Repository, pr_number: int) -> PullRequest:
    """Fetch pull request object from GitHub repository."""
    return gh_repo.get_pull(number=pr_number)


def create_pr(
    gh_repo: Repository,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
) -> str:
    """Create pull request and return its URL."""
    pr = gh_repo.create_pull(
        title=title, body=body, head=head_branch, base=base_branch
    )
    return pr.html_url
