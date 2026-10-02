"""SQLite store of already-notified job IDs."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from internbot.models import Job

DEFAULT_DB_PATH = "seen_jobs.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    company    TEXT NOT NULL,
    url        TEXT NOT NULL,
    first_seen TEXT NOT NULL
)
"""


class Storage:
    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("INTERNBOT_DB", DEFAULT_DB_PATH)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(_SCHEMA)
        self.conn.commit()

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        """Return jobs not yet marked seen, dropping duplicates within `jobs` itself."""
        seen_now: set[str] = set()
        new: list[Job] = []
        for job in jobs:
            if job.id in seen_now or self.is_seen(job.id):
                continue
            seen_now.add(job.id)
            new.append(job)
        return new

    def is_seen(self, job_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM seen_jobs WHERE id = ?", (job_id,)).fetchone()
        return row is not None

    def mark_seen(self, jobs: list[Job]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO seen_jobs (id, title, company, url, first_seen) "
                "VALUES (?, ?, ?, ?, ?)",
                [(j.id, j.title, j.company, j.url, now) for j in jobs],
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
