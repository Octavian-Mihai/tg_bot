"""Lever public postings (https://api.lever.co)."""
from __future__ import annotations

import logging

from internbot.models import Job
from internbot.sources.base import SourceError, get_json, location_matcher

log = logging.getLogger(__name__)
API = "https://api.lever.co/v0/postings/{slug}"


def _locations(raw: dict) -> list[str]:
    cats = raw.get("categories") or {}
    found = list(cats.get("allLocations") or [])
    if cats.get("location"):
        found.append(cats["location"])
    return found


def normalize(raw: dict, slug: str, company: str) -> Job:
    return Job(
        id=f"lever:{slug}:{raw['id']}",
        title=(raw.get("text") or "").strip(),
        company=company,
        location=((raw.get("categories") or {}).get("location") or "").strip(),
        url=raw["hostedUrl"],
        source="lever",
    )


def fetch_jobs(slug: str, company: str, locations: list[str]) -> list[Job]:
    data = get_json(API.format(slug=slug), params={"mode": "json"})
    if not isinstance(data, list):
        raise SourceError("unexpected Lever response shape")
    in_area = location_matcher(locations)
    jobs: list[Job] = []
    for raw in data:
        try:
            job = normalize(raw, slug, company)
        except KeyError as exc:
            log.warning("lever/%s: skipping malformed posting (missing %s)", slug, exc)
            continue
        if any(in_area(loc) for loc in _locations(raw)):
            jobs.append(job)
    log.info("lever/%s -> %d jobs in area (of %d)", slug, len(jobs), len(data))
    return jobs
