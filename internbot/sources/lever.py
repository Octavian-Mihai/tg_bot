"""Lever public postings (https://api.lever.co)."""
from __future__ import annotations

import logging

from internbot.models import Job
from internbot.sources.base import SourceError, get_json
from internbot.sources.common import build_job

log = logging.getLogger(__name__)
API = "https://api.lever.co/v0/postings/{slug}"


def _locations(raw: dict) -> list[str]:
    cats = raw.get("categories") or {}
    found = list(cats.get("allLocations") or [])
    if cats.get("location"):
        found.append(cats["location"])
    return found


def fetch_jobs(slug: str, company: str = "") -> list[Job]:
    data = get_json(API.format(slug=slug), params={"mode": "json"}, retries=2)
    if not isinstance(data, list):
        raise SourceError("unexpected Lever response shape")
    jobs: list[Job] = []
    for raw in data:
        try:
            url, pid = raw["hostedUrl"], raw["id"]
        except KeyError as exc:
            log.warning("lever/%s: skipping malformed posting (missing %s)", slug, exc)
            continue
        job = build_job(
            source="lever", ident=f"{slug}:{pid}", company=company or slug, title=raw.get("text") or "",
            location=" ; ".join(dict.fromkeys(_locations(raw))), url=url, posted=raw.get("createdAt"),
            description=f"{raw.get('descriptionPlain') or ''} {raw.get('additionalPlain') or ''}".strip(),
        )
        if job:
            jobs.append(job)
    log.info("lever/%s -> %d jobs in area (of %d)", slug, len(jobs), len(data))
    return jobs
