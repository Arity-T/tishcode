"""SQLite database for tracking PR fix attempts (server mode only)."""

import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_db_path = os.getenv("TC_DB_PATH")
if not _db_path:
    raise RuntimeError("Missing TC_DB_PATH in .env")
DB_PATH = Path(_db_path)


def get_connection() -> sqlite3.Connection:
    """Get database connection, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pr_fix_attempts (
            pr_key TEXT PRIMARY KEY,
            attempts INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


@contextmanager
def db_connection() -> Generator[sqlite3.Connection, Any, None]:
    """Context manager for database connection."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def make_pr_key(owner: str, repo: str, pr_number: int) -> str:
    """Create unique key for PR."""
    return f"{owner}/{repo}#{pr_number}"


def get_fix_attempts(owner: str, repo: str, pr_number: int) -> int:
    """Get current number of fix attempts for a PR."""
    pr_key = make_pr_key(owner, repo, pr_number)
    with db_connection() as conn:
        cursor = conn.execute(
            "SELECT attempts FROM pr_fix_attempts WHERE pr_key = ?", (pr_key,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0


def increment_fix_attempts(owner: str, repo: str, pr_number: int) -> int:
    """Increment fix attempts counter. Returns new count."""
    pr_key = make_pr_key(owner, repo, pr_number)
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO pr_fix_attempts (pr_key, attempts) VALUES (?, 1)
            ON CONFLICT(pr_key) DO UPDATE SET attempts = attempts + 1
            """,
            (pr_key,),
        )
        conn.commit()
        cursor = conn.execute(
            "SELECT attempts FROM pr_fix_attempts WHERE pr_key = ?", (pr_key,)
        )
        result = cursor.fetchone()
        assert result is not None
        return int(result[0])


def mark_pr_completed(owner: str, repo: str, pr_number: int) -> None:
    """Mark PR as completed (approved or max retries reached)."""
    pr_key = make_pr_key(owner, repo, pr_number)
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO pr_fix_attempts (pr_key, completed) VALUES (?, 1)
            ON CONFLICT(pr_key) DO UPDATE SET completed = 1
            """,
            (pr_key,),
        )
        conn.commit()


def is_pr_completed(owner: str, repo: str, pr_number: int) -> bool:
    """Check if PR processing is completed."""
    pr_key = make_pr_key(owner, repo, pr_number)
    with db_connection() as conn:
        cursor = conn.execute(
            "SELECT completed FROM pr_fix_attempts WHERE pr_key = ?", (pr_key,)
        )
        row = cursor.fetchone()
        return bool(row and row[0])
