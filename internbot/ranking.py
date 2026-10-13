"""Ranks postings best-first and says which résumé to send with each."""
from __future__ import annotations

from dataclasses import dataclass

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


def rank_jobs(jobs: list[Job], profile: Profile) -> list[Ranked]:
    """Montreal-area postings first, then highest chance, highest quality, and title for a stable order."""
    ranked = [Ranked(j, score_job(j, profile), choose_resume(j, profile)) for j in jobs]
    ranked.sort(key=lambda r: (not MONTREAL.search(r.job.location or ""), -r.score.chance, -r.score.quality, r.job.title.lower(), r.job.id))
    return ranked
