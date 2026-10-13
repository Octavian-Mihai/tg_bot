"""Ashby public job boards (https://api.ashbyhq.com)."""
from __future__ import annotations

import logging

from internbot.models import Job
from internbot.sources.base import get_json
from internbot.sources.common import build_job

log = logging.getLogger(__name__)
API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch_jobs(slug: str, company: str = "") -> list[Job]:
    data = get_json(API.format(slug=slug), params={"includeCompensation": "true"}, retries=2)
    jobs: list[Job] = []
    for raw in data.get("jobs", []):
        if raw.get("isListed") is False:
            continue
        url = raw.get("jobUrl") or raw.get("applyUrl")
        secondary = [(s.get("location") if isinstance(s, dict) else s) for s in raw.get("secondaryLocations") or []]
        location = " ; ".join(x for x in [raw.get("location"), *secondary] if x)
        comp = raw.get("compensation") or {}
        pay = comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary") or ""
        job = build_job(
            source="ashby", ident=f"{slug}:{url}", company=company or slug, title=raw.get("title") or "",
            location=location, url=url or "", description=raw.get("descriptionPlain") or "", compensation=pay,
        )
        if job:
            jobs.append(job)
    log.info("ashby/%s -> %d jobs in area", slug, len(jobs))
    return jobs
