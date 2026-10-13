"""Ranks postings best-first and says which résumé to send with each."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from internbot.models import Job
from internbot.places import MONTREAL
from internbot.profile import Profile
from internbot.resume import ResumeChoice, choose_resume
from internbot.scoring import Score, score_job


@dataclass(frozen=True)
class Ranked:
    job: Job
    score: Score
    resume: ResumeChoice


def _posted_ordinal(job: Job) -> int:
    try:
        return date.fromisoformat(job.posted).toordinal()
    except ValueError:
        return 0


def rank_jobs(jobs: list[Job], profile: Profile, priority_companies: tuple[str, ...] = ()) -> list[Ranked]:
    """Montreal-area first, then watchlist companies, then highest chance and quality, newest
    posting, and title for a stable order."""
    watch = {c.lower() for c in priority_companies}
    ranked = [Ranked(j, score_job(j, profile), choose_resume(j, profile)) for j in jobs]
    ranked.sort(key=lambda r: (
        not MONTREAL.search(r.job.location or ""),
        r.job.company.strip().lower() not in watch,
        -r.score.chance, -r.score.quality, -_posted_ordinal(r.job),
        r.job.title.lower(), r.job.id,
    ))
    return ranked
