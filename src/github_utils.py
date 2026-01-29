import time
import logging

import jwt
import requests
from github import Github
from github.Issue import Issue

GITHUB_API = "https://api.github.com"
logger = logging.getLogger("tishcode")


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


def get_issue(
    installation_token: str, owner: str, repo: str, issue_number: int
) -> Issue:
    """Fetch issue object from GitHub."""
    gh = Github(installation_token)
    repo_obj = gh.get_repo(f"{owner}/{repo}")
    return repo_obj.get_issue(number=issue_number)


def create_pr(
    installation_token: str,
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
) -> str:
    """Create pull request and return its URL."""
    gh = Github(installation_token)
    repo_obj = gh.get_repo(f"{owner}/{repo}")
    pr = repo_obj.create_pull(
        title=title, body=body, head=head_branch, base=base_branch
    )
    return pr.html_url
