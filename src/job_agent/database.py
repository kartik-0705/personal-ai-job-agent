
import sqlite3
from pathlib import Path

from src.job_agent.core import JobListing


DEFAULT_DB_PATH = Path("data/jobs.db")


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the local database and jobs table if they do not exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                retrieved_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Discovered',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_jobs(
    jobs: list[JobListing],
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Save jobs and return the number of newly inserted jobs."""
    initialize_database(db_path)
    path = Path(db_path)
    inserted = 0

    with sqlite3.connect(path) as connection:
        for job in jobs:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    title, company, location, url, source,
                    description, retrieved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.source,
                    job.description,
                    job.retrieved_at,
                ),
            )
            inserted += cursor.rowcount

    return inserted


def get_saved_jobs(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return saved jobs, newest database records first."""
    initialize_database(db_path)
    path = Path(db_path)

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, title, company, location, url, source,
                   description, retrieved_at, status, created_at
            FROM jobs
            ORDER BY id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]