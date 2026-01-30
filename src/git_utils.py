import logging
import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path

from git import Repo

logger = logging.getLogger("tishcode")


def get_unique_branch_name(local_repo: Repo, base_name: str) -> str:
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


@contextmanager
def clone_temp_repo(owner: str, repo: str, installation_token: str):
    """Context manager for cloning repository to temporary directory."""
    base_repos_path = os.getenv("TC_REPOS_BASE_PATH")
    if not base_repos_path:
        raise ValueError("TC_REPOS_BASE_PATH must be set in .env")
    unique_id = str(uuid.uuid4())[:8]
    repo_path = Path(base_repos_path) / f"{owner}_{repo}_{unique_id}"
    repo_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Using temporary directory: {repo_path}")

    repo_url = (
        f"https://x-access-token:{installation_token}@github.com/{owner}/{repo}.git"
    )

    try:
        logger.info(f"Cloning repository to {repo_path}")
        local_repo = Repo.clone_from(repo_url, repo_path)
        yield local_repo, repo_path
    finally:
        logger.debug(f"Cleaning up repository at {repo_path}")
        shutil.rmtree(repo_path, ignore_errors=True)
