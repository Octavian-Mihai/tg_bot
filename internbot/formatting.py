from __future__ import annotations

from internbot.models import Job
from internbot.notifier import TELEGRAM_MAX_LEN


def format_job(job: Job) -> str:
    where = f" — {job.location}" if job.location else ""
    return f"• {job.title}\n  {job.company}{where}\n  {job.url}"


def format_messages(jobs: list[Job], limit: int = TELEGRAM_MAX_LEN) -> list[str]:
    """Batch jobs into as few messages as possible, never exceeding `limit` chars."""
    if not jobs:
        return []
    header = f"{len(jobs)} new internship posting{'s' if len(jobs) != 1 else ''}"
    messages: list[str] = []
    current = header
    for job in jobs:
        entry = format_job(job)
        if len(entry) > limit:
            entry = entry[: limit - 1] + "…"
        candidate = f"{current}\n\n{entry}"
        if len(candidate) <= limit:
            current = candidate
        else:
            messages.append(current)
            current = entry
    messages.append(current)
    return messages
