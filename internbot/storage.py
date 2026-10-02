"""SQLite store of already-notified jobs."""
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
    first_seen TEXT NOT NULL,
    key        TEXT
)
"""


class Storage:
    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("INTERNBOT_DB", DEFAULT_DB_PATH)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        # DBs created before cross-source dedupe have no `key` column.
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(seen_jobs)")}
        if "key" not in cols:
            self.conn.execute("ALTER TABLE seen_jobs ADD COLUMN key TEXT")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_jobs_key ON seen_jobs(key)")

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        """Return jobs not yet seen: same id, or same (company, title) from a *different* source.

        The cross-source rule catches a posting listed on both Adzuna and a company board;
        two same-titled postings from one board are still treated as distinct.

        Duplicates inside `jobs` itself are dropped too; earlier entries win, so pass
        preferred sources (company boards) before aggregators (Adzuna).
        """
        batch_ids: set[str] = set()
        batch_keys: set[tuple[str, str]] = set()  # (key, source)
        new: list[Job] = []
        for job in jobs:
            other_source_in_batch = any(k == job.key and src != job.source for k, src in batch_keys)
            if job.id in batch_ids or other_source_in_batch or self.is_seen(job):
                continue
            batch_ids.add(job.id)
            batch_keys.add((job.key, job.source))
            new.append(job)
        return new

    def is_seen(self, job: Job) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM seen_jobs WHERE id = ? OR (key = ? AND id NOT LIKE ?)",
            (job.id, job.key, f"{job.source}:%")
        ).fetchone()
        return row is not None

    def mark_seen(self, jobs: list[Job]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO seen_jobs (id, title, company, url, first_seen, key) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(j.id, j.title, j.company, j.url, now, j.key) for j in jobs],
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
