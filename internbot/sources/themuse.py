"""The Muse: internships tagged Software Engineering. Unauthenticated callers are throttled, not blocked."""
from __future__ import annotations

import logging

from internbot.sources.base import FeedResult, SourceError, get_json
from internbot.sources.common import build_job
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

API = "https://www.themuse.com/api/public/jobs"
MAX_PAGES = 40


def scrape() -> FeedResult:
    jobs = []
    page_count = 1
    page = 1
    while page <= min(page_count, MAX_PAGES):
        try:
            res = get_json(API, params={"category": "Software Engineering", "level": "Internship", "page": page}, retries=2)
        except SourceError:
            if page == 1:
                raise
            break  # a later page failing keeps what we have
        page_count = res.get("page_count") or 1
        for r in res.get("results") or []:
            where = " ; ".join(l.get("name") for l in r.get("locations") or [] if l.get("name"))
            url = (r.get("refs") or {}).get("landing_page") or ""
            job = build_job(source="themuse", ident=url, company=(r.get("company") or {}).get("name") or "",
                            title=r.get("name") or "", location=where, url=url, description=html_to_text(r.get("contents")))
            if job:
                jobs.append(job)
        page += 1
    log.info("The Muse: %d matching internships", len(jobs))
    return FeedResult(jobs, [])
