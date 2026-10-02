"""Greenhouse public job boards (https://boards-api.greenhouse.io)."""
from __future__ import annotations

import logging

from internbot.models import Job
from internbot.sources.base import get_json, location_matcher

log = logging.getLogger(__name__)
API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def normalize(raw: dict, slug: str, company: str) -> Job:
    return Job(
        id=f"greenhouse:{slug}:{raw['id']}",
        title=(raw.get("title") or "").strip(),
        company=company,
        location=((raw.get("location") or {}).get("name") or "").strip(),
        url=raw["absolute_url"],
        source="greenhouse",
    )


def fetch_jobs(slug: str, company: str, locations: list[str]) -> list[Job]:
    data = get_json(API.format(slug=slug))
    in_area = location_matcher(locations)
    jobs: list[Job] = []
    for raw in data.get("jobs", []):
        try:
            job = normalize(raw, slug, company)
        except KeyError as exc:
            log.warning("greenhouse/%s: skipping malformed job (missing %s)", slug, exc)
            continue
        if in_area(job.location):
            jobs.append(job)
    log.info("greenhouse/%s -> %d jobs in area (of %d)", slug, len(jobs), len(data.get("jobs", [])))
    return jobs
