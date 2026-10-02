"""Adzuna job source (official API, Canada endpoint)."""
from __future__ import annotations

import logging
import os
import re
import sys

from dotenv import load_dotenv

from internbot.models import Job
from internbot.sources.base import SourceError, get_json

log = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/ca/search/{page}"
DEFAULT_KEYWORDS = [
    "software intern",
    "stagiaire développeur",
    "co-op software",
    "stagiaire informatique",
    "stagiaire",
    "stage informatique",
]
_TAG_RE = re.compile(r"<[^>]+>")


class AdzunaError(SourceError):
    pass


def normalize(raw: dict) -> Job:
    """Convert one Adzuna result into a Job."""
    return Job(
        id=f"adzuna:{raw['id']}",
        title=_TAG_RE.sub("", raw.get("title") or "").strip(),
        company=((raw.get("company") or {}).get("display_name") or "Unknown company").strip(),
        location=((raw.get("location") or {}).get("display_name") or "").strip(),
        url=raw["redirect_url"],
        source="adzuna",
    )


def fetch_jobs(
    app_id: str,
    app_key: str,
    keywords: list[str] | None = None,
    where: str = "Montreal, Quebec",
    distance_km: int = 30,
    max_days_old: int = 30,
    results_per_page: int = 50,
    timeout: float = 20,
) -> list[Job]:
    """Run one search per keyword and return de-duplicated jobs, newest first."""
    jobs: dict[str, Job] = {}
    for keyword in keywords or DEFAULT_KEYWORDS:
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": keyword,
            "where": where,
            "distance": distance_km,
            "max_days_old": max_days_old,
            "results_per_page": results_per_page,
            "sort_by": "date",
            "content-type": "application/json",
        }
        try:
            results = get_json(BASE_URL.format(page=1), params=params, timeout=timeout).get(
                "results", []
            )
        except SourceError as exc:
            raise AdzunaError(f"Adzuna {keyword!r}: {exc}") from None
        log.info("adzuna %r -> %d results", keyword, len(results))
        for raw in results:
            try:
                job = normalize(raw)
            except KeyError as exc:
                log.warning("skipping malformed Adzuna result (missing %s)", exc)
                continue
            jobs.setdefault(job.id, job)
    return list(jobs.values())


def fetch_from_env(**kwargs) -> list[Job]:
    load_dotenv()
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise AdzunaError("ADZUNA_APP_ID and ADZUNA_APP_KEY must be set")
    return fetch_jobs(app_id, app_key, **kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        found = fetch_from_env()
    except AdzunaError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    for j in found:
        print(f"{j.title} | {j.company} | {j.location}\n  {j.url}")
    print(f"\n{len(found)} jobs")
