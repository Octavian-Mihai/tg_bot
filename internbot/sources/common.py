"""The gate every scraper applies to a raw posting, and the Job it produces on success.

One shared builder so a field can't drift between fifteen scrapers.
"""
from __future__ import annotations

from dataclasses import replace

from internbot import places
from internbot.filters import is_wanted_title
from internbot.models import Job
from internbot.terms import OTHER_CYCLE, classify_posting


def build_job(
    *,
    source: str,
    ident: str,
    company: str,
    title: str,
    location: str,
    url: str,
    description: str = "",
    compensation: str = "",
    kind: str = "internship",
    term: str | None = None,
) -> Job | None:
    """Return a Job, or None when the title isn't a wanted internship, the location isn't
    workable from Montreal, or the posting is for the wrong hiring term.

    `source` is the channel ("workday"); `ident` makes the id unique within it. `term` lets a
    feed that guarantees its cycle skip classification.
    """
    title = (title or "").strip()
    if not url or not title:
        return None
    if not is_wanted_title(title, kind):
        return None
    if not places.in_area(location):
        return None
    term = term or classify_posting(title, description)
    if term == OTHER_CYCLE:
        return None
    return Job(
        id=f"{source}:{ident}",
        title=title,
        company=(company or "").strip() or "Unknown company",
        location=(location or "").strip(),
        url=url,
        source=source,
        description=description or "",
        term=term,
        compensation=compensation or "",
    )


def reclassify(job: Job, description: str) -> Job | None:
    """Attach a fetched description to a title-only Job, re-deriving its term. None if the
    description reveals it is for the wrong cycle."""
    term = classify_posting(job.title, description)
    if term == OTHER_CYCLE:
        return None
    return replace(job, description=description, term=term)
