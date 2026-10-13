"""Greenhouse public job boards (https://boards-api.greenhouse.io)."""
from __future__ import annotations

import logging
from dataclasses import replace

from internbot.models import Job
from internbot.sources.base import get_json, parallel_map
from internbot.sources.common import build_job, reclassify
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)
API = "https://boards-api.greenhouse.io/v1/boards/{slug}"


def fetch_jobs(slug: str, company: str = "") -> list[Job]:
    """Internships on one board that are in the area. Two passes: the board listing has no
    descriptions (asking for them returns megabytes), so only the survivors pay for one."""
    data = get_json(API.format(slug=slug) + "/jobs", retries=2)
    hits: list[Job] = []
    for raw in data.get("jobs", []):
        try:
            url, jid = raw["absolute_url"], raw["id"]
        except KeyError as exc:
            log.warning("greenhouse/%s: skipping malformed job (missing %s)", slug, exc)
            continue
        job = build_job(
            source="greenhouse", ident=f"{slug}:{jid}", company=company or slug,
            title=raw.get("title") or "", location=(raw.get("location") or {}).get("name") or "", url=url,
            posted=raw.get("first_published") or raw.get("updated_at"),
        )
        if job:
            hits.append(job)
    if not hits:
        return []

    if not company:  # the jobs endpoint never names the employer; the token is a poor stand-in
        try:
            name = get_json(API.format(slug=slug), retries=1).get("name") or slug
        except Exception:  # noqa: BLE001
            name = slug
        hits = [replace(j, company=name) for j in hits]

    def enrich(job: Job) -> Job | None:
        jid = job.id.rsplit(":", 1)[1]
        try:
            content = get_json(f"{API.format(slug=slug)}/jobs/{jid}", retries=1).get("content")
        except Exception:  # noqa: BLE001 - a failed description must not lose the job
            return job
        return reclassify(job, html_to_text(content))

    enriched = parallel_map(hits, enrich, workers=4)
    jobs = [j for j in enriched if j is not None]
    log.info("greenhouse/%s -> %d jobs in area", slug, len(jobs))
    return jobs
